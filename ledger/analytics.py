# ledger/analytics.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
import math

import pandas as pd
from zoneinfo import ZoneInfo
import sqlite3

LOCAL_TZ = ZoneInfo("America/Chicago")


# ---------- DB → DataFrame ----------

def _fetch_txns(conn: sqlite3.Connection, start_iso: Optional[str], end_iso: Optional[str]) -> pd.DataFrame:
    q = """
    SELECT date_utc, amount, currency, category, direction
    FROM transactions
    WHERE is_deleted=0
    """
    args: List[str] = []
    if start_iso:
        q += " AND date_utc >= ?"
        args.append(start_iso)
    if end_iso:
        q += " AND date_utc <= ?"
        args.append(end_iso)
    df = pd.read_sql_query(q, conn, params=args)
    if df.empty:
        return df
    # make tz-aware (UTC)
    df["date_utc"] = pd.to_datetime(df["date_utc"], utc=True)
    # local month label
    df["date_local"] = df["date_utc"].dt.tz_convert(LOCAL_TZ)
    df["month"] = df["date_local"].dt.to_period("M").astype(str)  # 'YYYY-MM'
    return df


# ---------- FX helpers (USD↔KRW only for MVP) ----------

def _get_fx_for_date(conn: sqlite3.Connection, base: str, quote: str, date_str: str) -> Optional[float]:
    """
    Return rate for given date (YYYY-MM-DD). If not found, fallback to the latest <= date.
    Stored series is daily; date_str derived from transaction UTC date.
    """
    row = conn.execute(
        """SELECT rate FROM fx_cache
           WHERE base=? AND quote=? AND date_utc=?
           ORDER BY date_utc DESC LIMIT 1""",
        (base, quote, date_str)
    ).fetchone()
    if row:
        return float(row["rate"])
    # fallback to latest prior
    row = conn.execute(
        """SELECT rate FROM fx_cache
           WHERE base=? AND quote=? AND date_utc<=?
           ORDER BY date_utc DESC LIMIT 1""",
        (base, quote, date_str)
    ).fetchone()
    return float(row["rate"]) if row else None


def _convert_amount(conn: sqlite3.Connection, amt: float, cur: str, base: str, date_utc: pd.Timestamp) -> Optional[float]:
    """
    Convert amt in 'cur' to 'base' using fx_cache (USD->KRW). Supports KRW↔USD.
    """
    cur = cur.upper()
    base = base.upper()
    if cur == base:
        return float(amt)

    d = date_utc.strftime("%Y-%m-%d")
    if base == "KRW" and cur == "USD":
        r = _get_fx_for_date(conn, "USD", "KRW", d)
        return None if r is None else float(amt) * r
    if base == "USD" and cur == "KRW":
        r = _get_fx_for_date(conn, "USD", "KRW", d)
        return None if r is None else float(amt) / r

    # unknown currency pair; skip
    return None


# ---------- Public API ----------

@dataclass
class TrendPoint:
    month: str
    value: float


@dataclass
class TrendSummary:
    category: str
    months: List[TrendPoint]
    mom_pct: Optional[float]
    theil_sen_per_month: Optional[float]
    mk_tau: Optional[float]
    mk_pvalue: Optional[float]


def monthly_category_totals(conn: sqlite3.Connection, base: str,
                            start_iso: Optional[str], end_iso: Optional[str]) -> Dict[str, List[TrendPoint]]:
    """
    Returns {category: [TrendPoint(month, value_in_base), ...]} for direction='debit' (spend).
    """
    df = _fetch_txns(conn, start_iso, end_iso)
    if df.empty:
        return {}

    # spend only (debit)
    df = df[df["direction"] == "debit"].copy()

    # convert to base currency
    conv_vals: List[Optional[float]] = []
    for i, r in df.iterrows():
        val = _convert_amount(conn, float(r["amount"]), str(r["currency"]), base, r["date_utc"])
        conv_vals.append(val)
    df["amount_base"] = conv_vals
    df = df.dropna(subset=["amount_base"])

    # aggregate by month/category
    grp = df.groupby(["month", "category"], as_index=False)["amount_base"].sum()
    # ensure sorted by month
    grp = grp.sort_values(["category", "month"])

    # pack as dict
    out: Dict[str, List[TrendPoint]] = {}
    for cat, g in grp.groupby("category"):
        points = [TrendPoint(month=m, value=float(v)) for m, v in zip(g["month"], g["amount_base"])]
        out[str(cat)] = points
    return out


# ---------- Stats: MoM%, Theil–Sen, Mann–Kendall ----------

def _mom_pct(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    prev = values[-2]
    curr = values[-1]
    if prev == 0:
        return None
    return (curr - prev) / prev * 100.0


def theil_sen_slope(values: List[float]) -> Optional[float]:
    """
    Median of pairwise slopes (t is 0..n-1 months). Returns unit per month.
    """
    n = len(values)
    if n < 2:
        return None
    slopes: List[float] = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            if (j - i) != 0:
                slopes.append((values[j] - values[i]) / (j - i))
    if not slopes:
        return None
    slopes.sort()
    mid = len(slopes) // 2
    if len(slopes) % 2 == 1:
        return slopes[mid]
    else:
        return 0.5 * (slopes[mid - 1] + slopes[mid])


def mann_kendall(values: List[float]) -> Tuple[Optional[float], Optional[float]]:
    """
    Returns (tau, pvalue). Simple MK test with normal approximation (ties ignored for MVP).
    """
    n = len(values)
    if n < 6:  # require at least 6 months, per our UX rule
        return None, None

    S = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = values[j] - values[i]
            S += 1 if diff > 0 else (-1 if diff < 0 else 0)

    # Kendall's tau
    denom = n * (n - 1) / 2
    tau = S / denom if denom else 0.0

    # Var(S) under H0 (no ties version)
    varS = n * (n - 1) * (2 * n + 5) / 18
    if varS <= 0:
        return tau, None

    if S > 0:
        z = (S - 1) / math.sqrt(varS)
    elif S < 0:
        z = (S + 1) / math.sqrt(varS)
    else:
        z = 0.0

    # two-sided p-value using erf
    # Phi(z) = 0.5 * (1 + erf(z / sqrt(2)))
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return tau, p


def summarize_trends(cat_points: Dict[str, List[TrendPoint]]) -> List[TrendSummary]:
    out: List[TrendSummary] = []
    for cat, points in cat_points.items():
        values = [p.value for p in points]
        mom = _mom_pct(values)
        ts = theil_sen_slope(values)
        tau, p = mann_kendall(values)
        out.append(TrendSummary(category=cat, months=points, mom_pct=mom,
                                theil_sen_per_month=ts, mk_tau=tau, mk_pvalue=p))
    # sort by latest month value desc
    out.sort(key=lambda s: s.months[-1].value if s.months else 0.0, reverse=True)
    return out

def mtd_spend(conn: sqlite3.Connection, base: str, now_utc: Optional[datetime] = None) -> Optional[float]:
    """
    이번 달 시작(현지 tz) ~ now_utc 사이의 debit 합계를 기준통화로 환산하여 반환.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # 현지(시카고) 월초 → UTC
    local_now = now_utc.astimezone(LOCAL_TZ)
    month_start_local = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start_utc = month_start_local.astimezone(timezone.utc)

    start_iso = month_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    df = _fetch_txns(conn, start_iso, end_iso)
    if df.empty:
        return 0.0

    df = df[df["direction"] == "debit"].copy()

    # 환산
    conv_vals = []
    for _, r in df.iterrows():
        v = _convert_amount(conn, float(r["amount"]), str(r["currency"]), base, r["date_utc"])
        if v is not None:
            conv_vals.append(v)
    return float(sum(conv_vals)) if conv_vals else 0.0