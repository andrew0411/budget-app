# app/pages/0_Dashboard.py
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.ui import (
    inject_css, metric_card, chip, bar_chart,
    get_dark_mode, set_dark_mode, fmt_money
)
from ledger.db import bootstrap, balances_in_base, list_budgets
from ledger.analytics import mtd_spend, month_actuals_by_category

st.title("🏠 Dashboard")

# ── Dark mode toggle + global CSS ────────────────────────────────────────────
with st.sidebar:
    dark = st.checkbox("🌙 Dark mode", value=get_dark_mode())
    set_dark_mode(dark)
inject_css()

# ── DB bootstrap ─────────────────────────────────────────────────────────────
DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

# ── 기준 통화 선택 ──────────────────────────────────────────────────────────
col0, col1 = st.columns([1, 1])
with col0:
    base = st.radio("기준 통화", ["KRW", "USD"], horizontal=True, index=0)
with col1:
    st.write(" ")

# ── 상단 메트릭: 총자산 / 이번달 지출 ───────────────────────────────────────
now_utc = datetime.now(timezone.utc)
bal = balances_in_base(conn, base=base)
total_assets = bal["total_base"]
mtd = mtd_spend(conn, base=base, now_utc=now_utc)

c1, c2 = st.columns(2)
with c1:
    metric_card("Total Assets", fmt_money(total_assets, base))
with c2:
    metric_card("Month-to-date Spend", fmt_money(mtd, base))

st.divider()

# ── Budget vs Actual (이 달) 요약 ───────────────────────────────────────────
st.subheader("📊 Budget summary (this month)")

now_local = datetime.now()  # month_actuals_by_category 내부에서 UTC 처리
year, month = now_local.year, now_local.month

# 실제 지출 합(기준통화) by category
actuals = month_actuals_by_category(conn, base=base, year=year, month=month)

# 예산: 해당 월 지정 + 공통(월 NULL) 모두 로드
brows = list_budgets(conn, month=f"{year:04d}-{month:02d}")

# 예산 dict (해당 월 지정 우선 → 없으면 공통)
monthly_key = f"{year:04d}-{month:02d}"
budget_dict = {}
# 1) 월 지정
for b in brows:
    if b["currency"] == base and b["month"] == monthly_key:
        budget_dict[str(b["category"])] = float(b["amount"])
# 2) 공통(없을 때만)
for b in brows:
    if b["currency"] == base and b["month"] is None:
        budget_dict.setdefault(str(b["category"]), float(b["amount"]))

# 진행률 표 생성
cats = sorted(set(actuals.keys()) | set(budget_dict.keys()))
rows = []
total_budget = 0.0
total_actual = 0.0
over_list = []

for cat in cats:
    a = float(actuals.get(cat, 0.0))
    bgt = float(budget_dict.get(cat, 0.0))
    total_actual += a
    total_budget += bgt
    pct = (a / bgt * 100.0) if bgt > 0 else None
    if bgt > 0 and a > bgt:
        over_list.append((cat, a - bgt))
    status = "—"
    if pct is not None:
        if pct >= 100:
            status = "🔴 Over"
        elif pct >= 80:
            status = "🟠 80%+"
        else:
            status = "🟢 OK"
    rows.append({
        "Category": cat,
        "Budget": fmt_money(bgt, base),
        "Actual": fmt_money(a, base),
        "Progress %": (None if pct is None else round(pct, 1)),
        "Status": status,
    })

if rows:
    df_prog = pd.DataFrame(rows)
    st.dataframe(df_prog, use_container_width=True)

    # 요약 배지/메트릭
    c3, c4, c5 = st.columns(3)
    c3.metric("Total Budget", fmt_money(total_budget, base))
    c4.metric("Total Actual", fmt_money(total_actual, base))
    if total_budget > 0:
        c5.metric("Total Progress", f"{(total_actual/total_budget*100):,.1f}%")
    else:
        c5.metric("Total Progress", "—")

    if over_list:
        over_list.sort(key=lambda x: x[1], reverse=True)
        top = ", ".join([f"{c} (+{fmt_money(d, base)})" for c, d in over_list[:3]])
        st.warning(f"과다 지출 카테고리: {top}")
    else:
        st.success("✅ 이 달은 아직 예산 초과가 없습니다.")
else:
    st.info("이번 달 예산이 없거나, 트랜잭션이 없습니다. Budget 페이지에서 예산을 먼저 입력하세요.")

st.divider()

# ── 계정별 잔액 표/차트 ────────────────────────────────────────────────────
st.subheader("계정별 잔액")

# 표는 보기 좋게 포맷된 문자열로, 차트는 별도 숫자 DataFrame으로 처리
table_rows = []
plot_rows = []
for it in bal["items"]:
    table_rows.append({
        "Account": it["name"],
        "Currency": it["currency"],
        "Balance (native)": fmt_money(it["balance_native"], it["currency"]),
        f"Balance ({base})": fmt_money(it["balance_base"], base),
    })
    plot_rows.append({
        "Account": it["name"],
        "Balance": float(it["balance_base"] or 0.0),
    })

df_table = pd.DataFrame(table_rows)
st.dataframe(df_table, use_container_width=True)

st.subheader("계정별 잔액 (기준 통화)")
df_plot = pd.DataFrame(plot_rows)
# 커스텀 파스텔 바 차트(Altair)
bar_chart(df_plot, x="Account", y="Balance")
