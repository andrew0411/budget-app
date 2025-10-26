from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional
import difflib

import pandas as pd
from zoneinfo import ZoneInfo

from .db import get_txns_between, get_or_create_account_full, find_account

LOCAL_TZ = ZoneInfo("America/Chicago")


@dataclass
class Mapping:
    date: str
    amount: str
    currency: Optional[str] = None
    payee: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class Defaults:
    currency: str = "KRW"
    category: str = "Uncategorized"
    direction: str = "auto"  # 'auto' | 'debit' | 'credit'

@dataclass
class Mapping:
    date: str
    amount: str
    currency: Optional[str] = None
    payee: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    account: Optional[str] = None       # NEW: 계정명 컬럼
    institution: Optional[str] = None   # NEW: 기관(은행/카드) 컬럼


def _to_iso_utc(x) -> Optional[str]:
    """Parse date string or pandas.Timestamp to ISO-8601 UTC (YYYY-MM-DDTHH:MM:SSZ)."""
    if pd.isna(x):
        return None
    ts = pd.to_datetime(x, errors="coerce")
    if pd.isna(ts):
        return None
    # Treat naive as local (America/Chicago), then convert to UTC
    if ts.tzinfo is None:
        ts = ts.tz_localize(LOCAL_TZ)
    else:
        ts = ts.tz_convert(LOCAL_TZ)
    ts = ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_payee(s: Optional[str]) -> str:
    if s is None:
        return ""
    return " ".join(str(s).strip().lower().split())


def _similar(a: str, b: str, threshold: float = 0.85) -> bool:
    if not a or not b:
        return False
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return ratio >= threshold


def dataframe_from_csv(file, encoding: Optional[str] = None) -> pd.DataFrame:
    """Read CSV to DataFrame; do not parse dates yet (let mapping decide)."""
    return pd.read_csv(file, encoding=encoding)


def map_df_to_txns(df: pd.DataFrame, mapping: Mapping, defaults: Defaults) -> List[Dict]:
    """Map arbitrary CSV columns to internal txn dicts; infer direction by amount sign if auto."""
    rows: List[Dict] = []
    for _, r in df.iterrows():
        try:
            date_iso = _to_iso_utc(r[mapping.date])
            if not date_iso:
                continue
            amount = float(r[mapping.amount])

            if mapping.currency and not pd.isna(r[mapping.currency]):
                currency = str(r[mapping.currency]).upper()
            else:
                currency = defaults.currency.upper()

            payee = (
                None
                if (not mapping.payee or pd.isna(r.get(mapping.payee, None)))
                else str(r[mapping.payee])
            )
            category = (
                None
                if (not mapping.category or pd.isna(r.get(mapping.category, None)))
                else str(r[mapping.category])
            )
            notes = (
                None
                if (not mapping.notes or pd.isna(r.get(mapping.notes, None)))
                else str(r[mapping.notes])
            )

            direction = defaults.direction
            amt = amount
            if defaults.direction == "auto":
                if amount < 0:
                    direction = "debit"
                    amt = abs(amount)
                else:
                    direction = "credit"
            else:
                amt = abs(amount)

            rows.append(
                {
                    "date_utc": date_iso,
                    "amount": float(amt),
                    "currency": currency,
                    "category": category or defaults.category,
                    "payee": payee,
                    "direction": direction,
                    "notes": notes,
                }
            )
        except Exception:
            # skip bad rows silently for MVP
            continue
    return rows


def mark_duplicates(conn, account_id: int, txns: List[Dict]) -> List[Dict]:
    """Mark duplicates by (same account, |date diff| ≤ 1d, same amount, similar payee)."""
    out: List[Dict] = []
    for t in txns:
        date_ts = pd.to_datetime(t["date_utc"], utc=True)
        start = (date_ts - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (date_ts + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        existing = get_txns_between(conn, account_id, start, end)
        dup = False
        npayee = _norm_payee(t.get("payee"))
        for e in existing:
            if abs(float(e["amount"]) - float(t["amount"])) < 1e-6:
                ep = _norm_payee(e["payee"])
                if (npayee == "" and ep == "") or _similar(npayee, ep):
                    dup = True
                    break
        tt = dict(t)
        tt["duplicate"] = dup
        out.append(tt)
    return out

def guess_institution_from_payee(payee: Optional[str]) -> Optional[str]:
    if not payee:
        return None
    s = str(payee).lower()
    # 간단한 키워드 맵 (원하는 대로 추가 가능)
    rules = {
        "chase": "Chase",
        "uwcu": "UWCU",
        "wcu": "UWCU",
        "kb": "KB",
        "국민": "KB",
        "신한": "Shinhan",
        "우리": "Woori",
        "삼성": "Samsung Card",
    }
    for k, v in rules.items():
        if k in s:
            return v
    return None

def resolve_account_id(conn, *, currency: str, account_name: Optional[str], institution: Optional[str],
                       payee: Optional[str], defaults_by_currency: dict, auto_create: bool = True) -> int:
    cur = (currency or "KRW").upper()
    # 1) (account_name, institution, currency)로 직접 조회
    row = find_account(conn, name=(account_name if account_name else None),
                       institution=(institution if institution else None), currency=cur)
    if row:
        return int(row["id"])
    # 2) institution만 있고 account_name 없음 → institution+currency로 조회
    if institution:
        row = find_account(conn, name=None, institution=institution, currency=cur)
        if row:
            return int(row["id"])
    # 3) payee에서 institution 추정
    inst2 = guess_institution_from_payee(payee) if payee else None
    if inst2:
        row = find_account(conn, name=None, institution=inst2, currency=cur)
        if row:
            return int(row["id"])
        if auto_create:
            return get_or_create_account_full(conn, name=None, institution=inst2, currency=cur, type="card", opening_balance=0.0)
    # 4) 필요시 자동 생성
    if auto_create and (account_name or institution):
        return get_or_create_account_full(conn, name=account_name, institution=institution, currency=cur, type="card", opening_balance=0.0)
    # 5) 마지막 fallback: 통화별 기본 계정
    return int(defaults_by_currency.get(cur))