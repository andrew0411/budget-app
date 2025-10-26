from pathlib import Path
from datetime import datetime, timezone

import streamlit as st

from ledger.db import bootstrap, ensure_default_accounts, add_transaction

st.title("⚡ Quick Add")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)
defaults = ensure_default_accounts(conn, currencies=("KRW","USD"))

with st.form("quick_add"):
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        dt = st.date_input("Date", datetime.now().date())  # local date
        tm = st.time_input("Time", datetime.now().time().replace(microsecond=0))
    with col2:
        amount = st.number_input("Amount", min_value=0.0, step=100.0, value=0.0, format="%.2f")
        direction = st.radio("Type", ["debit (지출)", "credit (수입)"], horizontal=True, index=0)
    with col3:
        currency = st.selectbox("Currency", ["KRW","USD"], index=0)
        category = st.text_input("Category", "Food")
    payee = st.text_input("Payee / Memo", "")
    notes = st.text_input("Notes", "")
    submit = st.form_submit_button("Add transaction")

if submit:
    # 현지 -> UTC ISO
    local_dt = datetime.combine(dt, tm).astimezone()
    utc_iso = local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    acc_id = defaults[currency]
    add_transaction(
        conn,
        date_utc=utc_iso,
        amount=amount,
        currency=currency,
        category=category or "Uncategorized",
        account_id=acc_id,
        direction="debit" if direction.startswith("debit") else "credit",
        payee=payee or None,
        notes=notes or None,
    )
    st.success("Saved! ⏎ 다음 입력을 바로 이어서 적어주세요.")
    st.experimental_rerun()
