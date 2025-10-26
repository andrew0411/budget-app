from pathlib import Path
import streamlit as st

from app.ui import inject_css, fmt_money
from ledger.db import (
    bootstrap,
    add_account,
    get_accounts,
    get_account_by_id,
    update_account,
    delete_account,
    count_account_transactions
)

st.title("🏦 Accounts (Banks/Cards)")
inject_css()

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)


# 삭제 확인 다이얼로그
@st.dialog("Delete Account")
def confirm_delete_dialog(acc_id: int, acc_name: str, txn_count: int):
    st.warning(f"Are you sure you want to delete **{acc_name}**?")

    if txn_count > 0:
        st.error(
            f"⚠️ This account has **{txn_count}** transaction(s). Deleting it will also delete all associated transactions.")
    else:
        st.info("This account has no transactions.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Confirm Delete", type="primary", use_container_width=True):
            deleted = delete_account(conn, acc_id)
            if deleted:
                st.success(f"✅ Account '{acc_name}' deleted successfully!")
                st.session_state.pop(f"delete_account_{acc_id}", None)
                st.rerun()
    with col2:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state.pop(f"delete_account_{acc_id}", None)
            st.rerun()


# 생성 성공 다이얼로그
@st.dialog("✅ Account Created")
def create_success_dialog():
    p = st.session_state.get("create_success_payload", {})
    name = p.get("name")
    inst = p.get("institution") or "(no bank)"
    ob = p.get("opening_balance", 0.0)
    cur = p.get("currency", "USD")

    st.success(f"Account created:\n\n**{name}** • {inst} • {fmt_money(ob, cur)}")

    if st.button("확인", type="primary", use_container_width=True):
        # Add 폼 초기화: key를 제거하면 위젯이 기본값/빈칸으로 돌아감
        for k in ("add_name", "add_inst", "add_currency", "add_type", "add_opening"):
            st.session_state.pop(k, None)
        # 다이얼로그 상태 정리
        st.session_state.pop("create_success_payload", None)
        st.session_state["show_create_success"] = False
        st.rerun()


# 탭으로 구성
tab1, tab2 = st.tabs(["➕ Add Account", "📝 Manage Accounts"])

# ============= TAB 1: Add Account =============
with tab1:
    st.subheader("Create New Account")

    # 생성 성공 플래그가 있으면 다이얼로그 표시
    if st.session_state.get("show_create_success"):
        create_success_dialog()

    with st.form("add_account", enter_to_submit=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            name = st.text_input("Account name*", placeholder="Chase Sapphire", key="add_name")
            institution = st.text_input("Institution (Bank)", placeholder="Chase", key="add_inst")
        with col2:
            currency = st.selectbox("Currency*", ["KRW", "USD"], index=1, key="add_currency")
            acc_type = st.selectbox(
                "Type",
                ["checking", "savings", "card", "cash", "brokerage", "other"],
                index=2,
                key="add_type"
            )
        with col3:
            opening_balance = st.number_input(
                "Opening balance",
                value=0.0,
                step=100.0,
                format="%.2f",
                key="add_opening"
            )

        submitted = st.form_submit_button("Create Account", type="primary")
        if submitted:
            if not name:
                st.error("Account name is required")
            else:
                add_account(
                    conn,
                    name=name,
                    institution=institution or None,
                    currency=currency,
                    type=acc_type,
                    opening_balance=opening_balance,
                )
                # 다음 렌더에서 성공 모달을 띄우기 위한 페이로드 저장
                st.session_state["create_success_payload"] = {
                    "name": name,
                    "institution": institution,
                    "currency": currency,
                    "opening_balance": opening_balance,
                }
                st.session_state["show_create_success"] = True
                st.rerun()

# ============= TAB 2: Manage Accounts =============
with tab2:
    st.subheader("Manage Existing Accounts")
    rows = get_accounts(conn)

    if not rows:
        st.info("No accounts yet. Create one in the 'Add Account' tab.")
    else:
        for r in rows:
            rd = dict(r)
            acc_id = int(rd["id"])
            acc_name = rd.get("name") or "(unnamed)"
            acc_inst = rd.get("institution") or "(no institution)"
            acc_cur = str(rd.get("currency", "")).upper()
            acc_type = rd.get("type") or "other"
            acc_balance = float(rd.get("opening_balance") or 0.0)

            # 해당 계정의 거래 개수
            txn_count = count_account_transactions(conn, acc_id)

            # Expander로 각 계정 표시
            with st.expander(f"**{acc_name}** ({acc_inst}) • {acc_cur} • {fmt_money(acc_balance, acc_cur)}",
                             expanded=False):
                st.caption(f"Account ID: {acc_id} | Type: {acc_type} | Transactions: {txn_count}")

                # 수정 폼
                with st.form(f"edit_account_{acc_id}"):
                    st.write("**Edit Account**")
                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input("Name", value=acc_name, key=f"name_{acc_id}")
                        new_inst = st.text_input("Institution",
                                                 value=acc_inst if acc_inst != "(no institution)" else "",
                                                 key=f"inst_{acc_id}")
                        new_currency = st.selectbox("Currency", ["KRW", "USD"],
                                                    index=0 if acc_cur == "KRW" else 1,
                                                    key=f"cur_{acc_id}")
                    with col2:
                        new_type = st.selectbox("Type",
                                                ["checking", "savings", "card", "cash", "brokerage", "other"],
                                                index=["checking", "savings", "card", "cash", "brokerage",
                                                       "other"].index(acc_type) if acc_type in ["checking", "savings",
                                                                                                "card", "cash",
                                                                                                "brokerage",
                                                                                                "other"] else 5,
                                                key=f"type_{acc_id}")
                        new_balance = st.number_input("Opening balance", value=acc_balance, step=100.0, format="%.2f",
                                                      key=f"bal_{acc_id}")

                    save_btn = st.form_submit_button("💾 Save Changes", type="primary")

                    if save_btn:
                        if not new_name:
                            st.error("Account name cannot be empty")
                        else:
                            updated = update_account(
                                conn,
                                acc_id,
                                name=new_name,
                                institution=new_inst or None,
                                currency=new_currency,
                                type=new_type,
                                opening_balance=new_balance
                            )
                            if updated:
                                st.success(f"✅ Account '{new_name}' updated successfully!")
                                st.rerun()
                            else:
                                st.warning("No changes made")

                # 삭제 버튼 (expander 하단)
                st.divider()
                if st.button("🗑️ Delete Account", key=f"del_{acc_id}", type="secondary"):
                    st.session_state[f"delete_account_{acc_id}"] = True

                # 다이얼로그 호출
                if st.session_state.get(f"delete_account_{acc_id}", False):
                    confirm_delete_dialog(acc_id, acc_name, txn_count)
