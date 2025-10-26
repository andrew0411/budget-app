# app/pages/8_Budget.py
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
from app.ui import inject_css, fmt_money

from ledger.db import bootstrap, list_budgets, upsert_budget
from ledger.analytics import month_actuals_by_category

st.title("📊 Budget vs Actual")
inject_css()

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

col1, col2, col3 = st.columns(3)
with col1:
    base = st.selectbox("기준 통화", ["KRW","USD"], index=0)
with col2:
    now = datetime.now()
    year = st.number_input("연도", min_value=2000, max_value=2100, value=now.year, step=1)
with col3:
    month = st.number_input("월", min_value=1, max_value=12, value=now.month, step=1)

# ── 예산 입력/수정 ───────────────────────────────────────────────────────────
st.subheader("예산 설정")
budgets = list_budgets(conn, month=f"{year:04d}-{month:02d}")
existing = {(b["category"], b["currency"]): float(b["amount"]) for b in budgets}

categories = sorted({k for k,_ in existing.keys()} | {"Food","Transport","Coffee","Groceries","Housing","Utilities","Shopping","Entertainment"})
rows = []
for cat in categories:
    amt = existing.get((cat, base), 0.0)
    rows.append({"Category": cat, f"Budget ({base})": amt})
df = pd.DataFrame(rows)

edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
if st.button("Save budgets"):
    saved = 0
    for _, r in edited.iterrows():
        cat = str(r["Category"])
        amt = float(r.get(f"Budget ({base})") or 0.0)
        if amt > 0:
            upsert_budget(conn, category=cat, amount=amt, currency=base, month=f"{year:04d}-{month:02d}")
            saved += 1
    st.success(f"Saved/updated {saved} budget row(s).")

# ── 실적 계산 ────────────────────────────────────────────────────────────────
st.subheader("이번 달 실적")
actuals = month_actuals_by_category(conn, base=base, year=int(year), month=int(month))

# 진행률 표/바
progress = []
total_budget = 0.0
total_actual = 0.0
for _, r in edited.iterrows():
    cat = str(r["Category"])
    b = float(r.get(f"Budget ({base})") or 0.0)
    a = float(actuals.get(cat, 0.0))
    total_budget += b
    total_actual += a
    pct = (a / b * 100.0) if b > 0 else None
    badge = "—"
    if pct is not None:
        if pct >= 100:
            badge = "🔴 Over"
        elif pct >= 80:
            badge = "🟠 80%+"
        else:
            badge = "🟢 OK"
    progress.append({
        "Category": cat,
        "Actual_raw": a,
        "Budget_raw": b,
        "Progress": (None if pct is None else round(pct, 1)),
        "Status": badge
    })

df_prog = pd.DataFrame(progress)

# 표시용 포맷 컬럼 추가 (원본 숫자 유지)
if not df_prog.empty:
    df_show = df_prog.copy()
    df_show[f"Actual ({base})"] = df_show["Actual_raw"].map(lambda x: fmt_money(float(x or 0.0), base))
    df_show[f"Budget ({base})"] = df_show["Budget_raw"].map(lambda x: fmt_money(float(x or 0.0), base))
    df_show = df_show[["Category", f"Actual ({base})", f"Budget ({base})", "Progress", "Status"]]
    st.dataframe(df_show, use_container_width=True)
else:
    st.dataframe(df_prog, use_container_width=True)

# 상단 요약 메트릭 (일관 포맷)
st.metric("Total Actual", fmt_money(total_actual, base))
st.metric("Total Budget", fmt_money(total_budget, base))
if total_budget > 0:
    st.metric("Total Progress", f"{total_actual/total_budget*100:,.1f}%")
