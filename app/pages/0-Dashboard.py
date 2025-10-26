# app/pages/0_Dashboard.py
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from ledger.db import bootstrap, balances_in_base, list_budgets
from ledger.analytics import mtd_spend, month_actuals_by_category

st.title("🏠 Dashboard")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

col0, col1 = st.columns([1,1])
with col0:
    base = st.radio("기준 통화", ["KRW", "USD"], horizontal=True, index=0)
with col1:
    st.write(" ")

# ── 상단 메트릭: 총자산 / 이번달 지출 ─────────────────────────────────────────
now_utc = datetime.now(timezone.utc)
bal = balances_in_base(conn, base=base)
total_assets = bal["total_base"]
mtd = mtd_spend(conn, base=base, now_utc=now_utc)

c1, c2 = st.columns(2)
c1.metric("Total Assets", f"{total_assets:,.2f} {base}")
c2.metric("Month-to-date Spend", f"{mtd:,.2f} {base}")

st.divider()

# ── Budget vs Actual (이 달) 요약 ────────────────────────────────────────────
st.subheader("📊 Budget summary (this month)")

now_local = datetime.now()   # month_actuals_by_category 내부에서 UTC 변환 처리
year, month = now_local.year, now_local.month

# 실제 지출 합(기준통화) by category
actuals = month_actuals_by_category(conn, base=base, year=year, month=month)

# 예산: 해당 월 지정 + 공통(월 NULL) 모두 로드
brows = list_budgets(conn, month=f"{year:04d}-{month:02d}")

# 예산 dict (해당 월 지정 우선 → 없으면 공통), 통화는 선택한 base만 사용
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
    b = float(budget_dict.get(cat, 0.0))
    total_actual += a
    total_budget += b
    pct = (a / b * 100.0) if b > 0 else None
    if b > 0 and a > b:
        over_list.append((cat, a - b))
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
        f"Budget ({base})": b,
        f"Actual ({base})": a,
        "Progress %": (None if pct is None else round(pct, 1)),
        "Status": status,
    })

if rows:
    df_prog = pd.DataFrame(rows)
    st.dataframe(df_prog, use_container_width=True)

    # 요약 배지
    c3, c4, c5 = st.columns(3)
    c3.metric("Total Budget", f"{total_budget:,.0f} {base}")
    c4.metric("Total Actual", f"{total_actual:,.0f} {base}")
    if total_budget > 0:
        c5.metric("Total Progress", f"{(total_actual/total_budget*100):,.1f}%")
    else:
        c5.metric("Total Progress", "—")

    if over_list:
        over_list.sort(key=lambda x: x[1], reverse=True)
        top = ", ".join([f"{c} (+{d:,.0f} {base})" for c, d in over_list[:3]])
        st.warning(f"과다 지출 카테고리: {top}")
    else:
        st.success("✅ 이 달은 아직 예산 초과가 없습니다.")
else:
    st.info("이번 달 예산이 없거나, 트랜잭션이 없습니다. Budget 페이지에서 예산을 먼저 입력하세요.")

st.divider()

# ── 계정별 잔액 표/차트 ────────────────────────────────────────────────────
st.subheader("계정별 잔액")

rows = []
for it in bal["items"]:
    rows.append({
        "Account": it["name"],
        "Currency": it["currency"],
        "Balance (native)": it["balance_native"],
        f"Balance ({base})": it["balance_base"],
    })
df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

st.subheader("계정별 잔액 (기준 통화)")
chart_df = df[["Account", f"Balance ({base})"]].set_index("Account").fillna(0.0)
st.bar_chart(chart_df)
