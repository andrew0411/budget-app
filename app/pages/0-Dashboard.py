# app/pages/0_Dashboard.py
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from ledger.db import bootstrap, balances_in_base
from ledger.analytics import mtd_spend

st.title("🏠 Dashboard")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

col0, col1 = st.columns([1,1])
with col0:
    base = st.radio("기준 통화", ["KRW", "USD"], horizontal=True, index=0)
with col1:
    st.write(" ")

# 총자산/MTD 지출
now_utc = datetime.now(timezone.utc)
bal = balances_in_base(conn, base=base)
total_assets = bal["total_base"]
mtd = mtd_spend(conn, base=base, now_utc=now_utc)

c1, c2 = st.columns(2)
c1.metric("Total Assets", f"{total_assets:,.2f} {base}")
c2.metric("Month-to-date Spend", f"{mtd:,.2f} {base}")

# 계정별 표/차트
rows = []
for it in bal["items"]:
    rows.append({
        "Account": it["name"],
        "Currency": it["currency"],
        "Balance (native)": it["balance_native"],
        f"Balance ({base})": it["balance_base"],
    })
df = pd.DataFrame(rows)

st.subheader("계정별 잔액")
st.dataframe(df, use_container_width=True)

st.subheader("계정별 잔액 (기준 통화)")
chart_df = df[["Account", f"Balance ({base})"]].set_index("Account").fillna(0.0)
st.bar_chart(chart_df)
