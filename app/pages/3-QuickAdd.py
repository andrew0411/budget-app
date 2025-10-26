# app/pages/3_QuickAdd.py
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st

from ledger.db import bootstrap, ensure_default_accounts, add_transaction, get_accounts

st.title("⚡ Quick Add")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)
defaults = ensure_default_accounts(conn, currencies=("KRW","USD"))

col0, col1 = st.columns([1,1])
with col0:
    currency = st.selectbox("Currency", ["KRW","USD"], index=0)
with col1:
    # 통화에 맞는 계정만 노출 (은행/카드 구분은 name/institution에 반영)
    acc_rows = [r for r in get_accounts(conn) if r["currency"].upper()==currency]
    if not acc_rows:
        st.warning("해당 통화의 계정이 없습니다. Accounts 페이지에서 먼저 생성하세요.")
        st.stop()
    # 라벨: "이름 (기관)"
    options = {f'{r["name"]} ({r["currency"]}{", "+r["name"] if not r["name"] else ""})' : r["id"] for r in acc_rows}
    # 더 친절한 라벨
    options = {f'{r["name"]} — {r["currency"]} / {r["id"]}' if r.get("name") else f'Account {r["id"]} — {r["currency"]}': r["id"] for r in acc_rows}
    # 기본 선택: 통화별 Default 계정
    default_id = defaults.get(currency)
    default_label = next((k for k,v in options.items() if v == default_id), list(options.keys())[0])
    account_id = st.selectbox("Account (Bank/Card)", list(options.keys()), index=list(options.keys()).index(default_label))
    account_id = options[account_id]

with st.form("quick_add"):
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        dt = st.date_input("Date", datetime.now().date())
        tm = st.time_input("Time", datetime.now().time().replace(microsecond=0))
    with col2:
        amount = st.number_input("Amount", min_value=0.0, step=100.0, value=0.0, format="%.2f")
        direction = st.radio("Type", ["debit (지출)", "credit (수입)"], horizontal=True, index=0)
    with col3:
        category = st.text_input("Category", "Food")
    payee = st.text_input("Payee / Memo", "")
    notes = st.text_input("Notes", "")
    submit = st.form_submit_button("Add transaction")

if submit:
    local_dt = datetime.combine(dt, tm).astimezone()
    utc_iso = local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    add_transaction(
        conn,
        date_utc=utc_iso,
        amount=amount,
        currency=currency,
        category=category or "Uncategorized",
        account_id=int(account_id),
        direction="debit" if direction.startswith("debit") else "credit",
        payee=payee or None,
        notes=notes or None,
    )
    st.success("Saved! Enter 키로 바로 다음 입력을 이어갈 수 있어요.")
    st.experimental_rerun()
