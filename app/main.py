from pathlib import Path
from datetime import datetime, timezone

import streamlit as st

from ledger.db import (
    bootstrap,
    count_rows,
    add_account,
    add_transaction,
    ensure_default_accounts,
)

st.set_page_config(page_title="Budget App", page_icon="💸", layout="wide")

st.title("💸 Budget App (Pastel Ledger)")
st.caption("Local-first, beginner-friendly personal finance tracker")

# --- DB bootstrap ---
DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")

with st.sidebar:
    st.subheader("Database")
    try:
        conn = bootstrap(DB_PATH)
        # 기본 계정 자동 생성 (KRW, USD)
        defaults = ensure_default_accounts(conn, currencies=("KRW", "USD"))

        acc_n = count_rows(conn, "accounts")
        txn_n = count_rows(conn, "transactions")
        st.success(f"DB 연결 OK · accounts={acc_n}, transactions={txn_n}")
    except Exception as e:
        st.error(f"DB 오류: {e}")

    if st.button("샘플 데이터 추가 (계정+거래 1건)"):
        try:
            # KRW 기본 계정 확인
            krw_acc_id = defaults.get("KRW")
            if not krw_acc_id:
                krw_acc_id = add_account(
                    conn,
                    name="Default KRW",
                    institution="Local",
                    currency="KRW",
                    type="cash",
                    opening_balance=0.0,
                )

            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            add_transaction(
                conn,
                date_utc=now_utc,
                amount=12500,
                currency="KRW",
                category="Food",
                account_id=krw_acc_id,
                direction="debit",
                payee="Sample Cafe",
                notes="Scaffold sample",
            )
            st.success("샘플 입력 완료! 새로고침하면 카운트가 증가합니다.")
        except Exception as e:
            st.error(f"샘플 입력 실패: {e}")

c1, c2, c3 = st.columns(3)
c1.metric("Total Assets (base)", "—", help="KRW or USD after data & FX")
c2.metric("Month-to-date Spend", "—")
c3.metric("FX (USD→KRW)", "—", help="FRED DEXKOUS as-of appears later")

st.success("Scaffold OK. Next: CSV import, FX provider, analytics.")
