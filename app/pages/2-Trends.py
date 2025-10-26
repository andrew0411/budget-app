# app/pages/2_Trends.py
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from ledger.db import bootstrap
from ledger.analytics import monthly_category_totals, summarize_trends

st.title("📈 Trends & Analytics")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

# Controls
col1, col2, col3 = st.columns(3)
with col1:
    base = st.selectbox("기준 통화 (Base)", ["KRW", "USD"], index=0)
with col2:
    months_back = st.slider("분석 범위(개월)", min_value=3, max_value=24, value=12, step=1)
with col3:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=months_back * 31)
    st.write(f"범위: {start_dt.date()} ~ {end_dt.date()}")

start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

cat_points = monthly_category_totals(conn, base=base, start_iso=start_iso, end_iso=end_iso)
summary = summarize_trends(cat_points)

if not summary:
    st.info("표시할 데이터가 없습니다. Import 페이지에서 CSV를 추가해 주세요.")
    st.stop()

# Chart: stacked bars by month (top N categories)
N = st.slider("상위 카테고리 N", 3, 10, 5)
top_cats = [s.category for s in summary[:N]]

# Build a pivot table: rows=month, cols=category, values=amount
rows = []
for cat, pts in cat_points.items():
    if cat not in top_cats:
        continue
    for p in pts:
        rows.append({"month": p.month, "category": cat, "amount": p.value})
df = pd.DataFrame(rows)
pivot = df.pivot_table(index="month", columns="category", values="amount", aggfunc="sum").fillna(0.0)
pivot = pivot.sort_index()

st.subheader("월별 합계 (상위 카테고리)")
st.bar_chart(pivot)

# Table: trend badges (MoM %, Theil–Sen per month, MK)
def _mk_badge(tau, p):
    if tau is None or p is None:
        return "—"
    if p < 0.1:
        return "↑ (p<0.1)" if tau > 0 else "↓ (p<0.1)"
    return "—"

table = []
for s in summary:
    vals = [p.value for p in s.months]
    latest = vals[-1] if vals else 0.0
    table.append({
        "Category": s.category,
        f"Latest ({base})": latest,
        "MoM %": None if s.mom_pct is None else round(s.mom_pct, 1),
        "Theil–Sen (/mo)": None if s.theil_sen_per_month is None else round(s.theil_sen_per_month, 2),
        "MK": _mk_badge(s.mk_tau, s.mk_pvalue),
    })

st.subheader("트렌드 요약")
st.dataframe(pd.DataFrame(table))
st.caption("MK: Mann–Kendall. p<0.1인 경우만 ↑/↓로 표시 (표본 적을 때는 —). Theil–Sen은 월당 변화량.")
