# app/pages/4_Accounts.py
from pathlib import Path
import streamlit as st

from ledger.db import bootstrap, add_account, get_accounts

st.title("🏦 Accounts (Banks/Cards)")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

st.subheader("Add Account / Card")
with st.form("add_account"):
    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input("Account name", "Chase Sapphire")
        institution = st.text_input("Institution (Bank)", "Chase")
    with col2:
        currency = st.selectbox("Currency", ["KRW","USD"], index=1)
        acc_type = st.selectbox("Type", ["checking","savings","card","cash","brokerage","other"], index=2)
    with col3:
        opening_balance = st.number_input("Opening balance", value=0.0, step=100.0, format="%.2f")
    submitted = st.form_submit_button("Create")
    if submitted:
        add_account(conn, name=name, institution=institution, currency=currency, type=acc_type, opening_balance=opening_balance)
        st.success("Account created.")
        st.experimental_rerun()

st.subheader("Existing Accounts")
rows = get_accounts(conn)
if rows:
    st.table([{"id": r["id"], "name": r["name"], "institution": r.get("institution"), "currency": r["currency"]} for r in rows])
else:
    st.info("No accounts yet.")
