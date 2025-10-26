# ledger/analytics.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from math import erf, sqrt
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

def _fetch_txns_joined(conn: sqlite3.Connection, start_iso: Optional[str], end_iso: Optional[str]) -> pd.DataFrame:
    q = """
    SELECT t.date_utc, t.amount, t.currency, t.category, t.direction,
           a.institution, a.name AS account_name
    FROM transactions t
    JOIN accounts a ON a.id = t.account_id
    WHERE t.is_deleted=0
    """
    args = []
    if start_iso:
        q += " AND t.date_utc >= ?"
        args.append(start_iso)
    if end_iso:
        q += " AND t.date_utc <= ?"
        args.append(end_iso)

    df = pd.read_sql_query(q, conn, params=args)
    if df.empty:
        return df
    df["date_utc"] = pd.to_datetime(df["date_utc"], utc=True)
    return df

def spend_by_institution(conn: sqlite3.Connection, base: str,
                         start_iso: Optional[str], end_iso: Optional[str]) -> pd.DataFrame:
    """
    기관(institution)별 지출 합계/건수 (direction='debit'만), 기준 통화로 환산하여 반환.
    Columns: institution, amount_base, count
    """
    df = _fetch_txns_joined(conn, start_iso, end_iso)
    if df.empty:
        return df

    df = df[df["direction"]=="debit"].copy()
    conv = []
    for _, r in df.iterrows():
        v = _convert_amount(conn, float(r["amount"]), str(r["currency"]), base, r["date_utc"])
        if v is not None:
            conv.append(v)
        else:
            conv.append(float("nan"))
    df["amount_base"] = conv
    df = df.dropna(subset=["amount_base"])
    grp = df.groupby(df["institution"].fillna("Unknown"), as_index=False).agg(
        amount_base=("amount_base","sum"), count=("amount_base","count")
    )
    grp = grp.sort_values("amount_base", ascending=False)
    return grp

def month_actuals_by_category(conn: sqlite3.Connection, base: str, year: int, month: int) -> Dict[str, float]:
    """
    해당 월(현지 tz 기준)의 카테고리별 지출합(=debit 합계)을 기준통화로 환산해서 반환.
    ZoneInfo(예: America/Chicago) 사용: localize 불가 → tz-aware로 직접 생성.
    """
    from datetime import datetime, timezone

    LOCAL_TZ = ZoneInfo("America/Chicago")  # 환경에 맞추어 필요 시 설정
    # tz-aware 시작/종료
    start_local = datetime(year=year, month=month, day=1, tzinfo=LOCAL_TZ)
    if month == 12:
        end_local = datetime(year=year + 1, month=1, day=1, tzinfo=LOCAL_TZ)
    else:
        end_local = datetime(year=year, month=month + 1, day=1, tzinfo=LOCAL_TZ)

    start_iso = start_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 기존 내부 헬퍼를 사용한다고 가정 (_fetch_txns, _convert_amount)
    df = _fetch_txns(conn, start_iso, end_iso)
    if df.empty:
        return {}

    df = df[df["direction"] == "debit"].copy()
    conv = []
    for _, r in df.iterrows():
        v = _convert_amount(conn, float(r["amount"]), str(r["currency"]), base, r["date_utc"])
        conv.append(v)
    df["amount_base"] = conv
    df = df.dropna(subset=["amount_base"])
    grp = df.groupby("category", as_index=False)["amount_base"].sum()
    return {str(r["category"]): float(r["amount_base"]) for _, r in grp.iterrows()}

def _phi(z: float) -> float:
    # 표준정규 CDF
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))

def mann_kendall(y: pd.Series) -> Optional[Dict[str, float]]:
    """
    Mann–Kendall trend test (ties 무시한 간단 버전).
    y: 시계열 값(시간 순 정렬). 길이 n<3이면 None.
    반환: {"tau": τ, "z": z, "p": p_two_sided}
    """
    y = y.dropna()
    n = len(y)
    if n < 3:
        return None
    vals = y.values
    # S = sum_{j>i} sign(yj - yi)
    S = 0
    for i in range(n - 1):
        diff = vals[i + 1:] - vals[i]
        S += (diff > 0).sum() - (diff < 0).sum()
    # Kendall's tau
    denom = n * (n - 1) / 2.0
    tau = S / denom if denom else 0.0
    # Var(S) (ties 무시)
    varS = (n * (n - 1) * (2 * n + 5)) / 18.0
    if varS == 0:
        return {"tau": tau, "z": 0.0, "p": 1.0}
    z = (S - 1) / sqrt(varS) if S > 0 else (S + 1) / sqrt(varS) if S < 0 else 0.0
    p = 2.0 * (1.0 - _phi(abs(z)))
    return {"tau": float(tau), "z": float(z), "p": float(max(min(p, 1.0), 0.0))}

def theil_sen_slope(y: pd.Series) -> Optional[float]:
    """
    Theil–Sen: 모든 (j>i) 쌍의 (y[j]-y[i])/(j-i) 중앙값.
    y: 시계열 값(시간 순 정렬). 길이 n<2이면 None.
    반환: 월당 증가액(기준통화 단위).
    """
    y = y.dropna()
    n = len(y)
    if n < 2:
        return None
    vals = y.values
    slopes = []
    for i in range(n - 1):
        dy = vals[i + 1:] - vals[i]
        dx = (pd.Series(range(i + 1, n)).values - i).astype(float)  # 월 간격: 1,2,...
        slopes.extend((dy / dx).tolist())
    return float(pd.Series(slopes).median()) if slopes else None

def monthly_spend_series(conn, base: str = "KRW", months: int = 24, category: Optional[str] = None) -> pd.Series:
    """
    최근 'months'개월의 월별 지출 합계(기준통화) 시계열을 반환.
    category 지정 시 해당 카테고리만 필터. 없으면 전체 지출.
    index: 'YYYY-MM' 문자열, value: 금액(float)
    """
    # ── 기간 경계(UTC) 계산
    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - pd.Timedelta(days=31 * months)
    start_iso = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── 참조용 pandas Timestamp (to_period 사용 위해)
    now_ts = pd.Timestamp(now_utc)  # ✅ pandas Timestamp로 변환
    start_period = (now_ts - pd.DateOffset(months=months - 1)).to_period("M")
    end_period = now_ts.to_period("M")
    full_idx = pd.period_range(start=start_period, end=end_period, freq="M").astype(str)

    df = _fetch_txns(conn, start_iso, end_iso)
    if df.empty:
        return pd.Series([0.0] * len(full_idx), index=full_idx)

    # 지출만, 카테고리 필터
    df = df[df["direction"] == "debit"].copy()
    if category:
        df = df[df["category"] == category]
    if df.empty:
        return pd.Series([0.0] * len(full_idx), index=full_idx)

    # 기준통화 환산
    conv = []
    for _, r in df.iterrows():
        v = _convert_amount(conn, float(r["amount"]), str(r["currency"]), base, r["date_utc"])
        conv.append(v)
    df["amount_base"] = conv
    df = df.dropna(subset=["amount_base"]).copy()
    if df.empty:
        return pd.Series([0.0] * len(full_idx), index=full_idx)

    # 월(YYYY-MM)로 집계
    df["ym"] = pd.to_datetime(df["date_utc"]).dt.to_period("M").astype(str)
    s = df.groupby("ym")["amount_base"].sum().sort_index()

    # 빈 달 0 채우기
    s = s.reindex(full_idx, fill_value=0.0)
    return s

def trend_summary(conn, base: str, months: int, category: Optional[str] = None) -> Dict[str, Optional[float]]:
    """
    월별 시계열 → Mann–Kendall(τ,p) + Theil–Sen(slope) + 최근/평균.
    slope 단위: 기준통화/월.
    """
    s = monthly_spend_series(conn, base=base, months=months, category=category)
    mk = mann_kendall(s)
    slope = theil_sen_slope(s)
    res = {
        "last": float(s.iloc[-1]) if len(s) else None,
        "mean": float(s.mean()) if len(s) else None,
        "tau": mk["tau"] if mk else None,
        "p": mk["p"] if mk else None,
        "slope": slope
    }
    return res