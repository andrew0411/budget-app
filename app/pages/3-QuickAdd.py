from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from app.ui import inject_css, fmt_money

from ledger.db import bootstrap, ensure_default_accounts, add_transaction, get_accounts

st.title("⚡ Quick Add")
inject_css()

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)
defaults = ensure_default_accounts(conn, currencies=("KRW", "USD"))

# 통화 선택
col0, col1 = st.columns([1, 1])
with col0:
    currency = st.selectbox("Currency", ["KRW", "USD"], index=0)

# 계정 선택(해당 통화만)
with col1:
    # 1) 모든 계정 로드 후 dict로 변환
    rows = get_accounts(conn)
    acc_all = [dict(r) for r in rows]
    # 2) 통화 필터 (키 없을 수도 있으므로 .get)
    acc_rows = [r for r in acc_all if str(r.get("currency", "")).upper() == currency]

    if not acc_rows:
        st.warning("해당 통화의 계정이 없습니다. Accounts 페이지에서 먼저 생성하세요.")
        st.stop()

    # 보기 좋은 라벨 구성 (dict 기반)
    labels = []
    for r in acc_rows:
        aid = int(r["id"])
        name = r.get("name") or f"Account {aid}"
        inst = r.get("institution") or ""
        cur = str(r.get("currency", "")).upper()
        label = f"{aid} — {name} ({inst}) [{cur}]"
        labels.append((label, aid))

    label_list = [L for L, _ in labels]
    # 기본 선택: 통화별 기본 계정(없으면 첫 번째)
    default_id = defaults.get(currency)
    default_label_idx = next((i for i, (_, aid) in enumerate(labels) if default_id and aid == int(default_id)), 0)
    chosen_label = st.selectbox("Account (Bank/Card)", label_list, index=default_label_idx)
    account_id = next(aid for L, aid in labels if L == chosen_label)

with st.form("quick_add"):
    col1, col2, col3 = st.columns([1, 1, 1])
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
    st.success(f"Saved {fmt_money(amount, currency)} to account {account_id}. Enter 키로 다음 입력을 이어갈 수 있어요.")
    st.experimental_rerun()
