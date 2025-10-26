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
    count_account_transactions,
    account_balances_native,
)

st.title("🏦 Accounts (Banks/Cards)")
inject_css()

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)


# ------------------------------
# Dialogs
# ------------------------------
@st.dialog("Delete Account")
def confirm_delete_dialog(acc_id: int, acc_name: str, txn_count: int):
    st.warning(f"Are you sure you want to delete **{acc_name}**?")

    if txn_count > 0:
        st.error(
            f"⚠️ This account has **{txn_count}** transaction(s). Deleting it will also delete all associated transactions."
        )
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


@st.dialog("✅ Account Created")
def create_success_dialog():
    p = st.session_state.get("create_success_payload", {})
    name = p.get("name")
    inst = p.get("institution") or "(no bank)"
    ob = p.get("opening_balance", 0.0)
    cur = p.get("currency", "USD")

    st.success(f"Account created:\n\n**{name}** • {inst} • {fmt_money(ob, cur)}")

    if st.button("확인", type="primary", use_container_width=True):
        # ✅ 폼 기본값을 session_state로만 제어 (위젯 측 기본값과 중복 지정 금지)
        st.session_state.update({
            "add_name": "",
            "add_inst": "",
            "add_currency": "USD",
            "add_type": "card",
            "add_opening": 0.0,
        })
        st.session_state.pop("create_success_payload", None)
        st.session_state["show_create_success"] = False
        st.rerun()


# ------------------------------
# Tabs
# ------------------------------
tab1, tab2 = st.tabs(["➕ Add Account", "📝 Manage Accounts"])

# ============= TAB 1: Add Account =============
with tab1:
    st.subheader("Create New Account")

    # ⚙️ 위젯 기본값은 무조건 session_state로만 관리 (경고 방지)
    st.session_state.setdefault("add_name", "")
    st.session_state.setdefault("add_inst", "")
    st.session_state.setdefault("add_currency", "USD")
    st.session_state.setdefault("add_type", "card")
    st.session_state.setdefault("add_opening", 0.0)

    if st.session_state.get("show_create_success"):
        create_success_dialog()

    with st.form("add_account", enter_to_submit=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            name = st.text_input("Account name*", placeholder="Chase Sapphire", key="add_name")
            institution = st.text_input("Institution (Bank)", placeholder="Chase", key="add_inst")
        with col2:
            # ❌ index/value 지정 금지, ✅ key만 사용 (값은 session_state가 가짐)
            currency = st.selectbox("Currency*", ["KRW", "USD"], key="add_currency")
            acc_type = st.selectbox(
                "Type",
                ["checking", "savings", "card", "cash", "brokerage", "other"],
                key="add_type"
            )
        with col3:
            opening_balance = st.number_input(
                "Opening balance",
                step=100.0,
                format="%.2f",
                key="add_opening",
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
        # 현재 잔액(= opening + txns) 맵
        bal_items = account_balances_native(conn)
        bal_map = {it["account_id"]: float(it["balance_native"]) for it in bal_items}

        def _ensure_full_row(rdict):
            """필수 컬럼 누락 시 DB에서 재조회해 보강."""
            needed = {"institution", "type", "opening_balance"}
            if needed.issubset(set(rdict.keys())):
                return rdict
            full = get_account_by_id(conn, int(rdict["id"]))
            return dict(full) if full else rdict

        for r in rows:
            rd = _ensure_full_row(dict(r))

            acc_id = int(rd["id"])
            acc_name = rd.get("name") or "(unnamed)"
            acc_inst = (rd.get("institution") or "").strip() or "(no institution)"
            acc_cur = str(rd.get("currency", "")).upper()
            acc_type = rd.get("type") or "other"
            acc_opening = float(rd.get("opening_balance") or 0.0)
            acc_current_balance = bal_map.get(acc_id, acc_opening)

            with st.expander(
                f"**{acc_name}** ({acc_inst}) • {acc_cur} • {fmt_money(acc_current_balance, acc_cur)}",
                expanded=False
            ):
                st.caption(
                    f"Account ID: {acc_id} | Type: {acc_type} | "
                    f"Opening: {fmt_money(acc_opening, acc_cur)} | "
                    f"Current: {fmt_money(acc_current_balance, acc_cur)}"
                )

                txn_count = count_account_transactions(conn, acc_id)

                with st.form(f"edit_account_{acc_id}"):
                    st.write("**Edit Account**")
                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input("Name", value=acc_name, key=f"name_{acc_id}")
                        new_inst = st.text_input(
                            "Institution",
                            value="" if acc_inst == "(no institution)" else acc_inst,
                            key=f"inst_{acc_id}"
                        )
                        new_currency = st.selectbox(
                            "Currency", ["KRW", "USD"],
                            index=0 if acc_cur == "KRW" else 1,
                            key=f"cur_{acc_id}"
                        )
                    with col2:
                        new_type = st.selectbox(
                            "Type",
                            ["checking", "savings", "card", "cash", "brokerage", "other"],
                            index=["checking", "savings", "card", "cash", "brokerage", "other"].index(acc_type)
                            if acc_type in ["checking", "savings", "card", "cash", "brokerage", "other"] else 5,
                            key=f"type_{acc_id}"
                        )
                        new_balance = st.number_input(
                            "Opening balance",
                            value=float(acc_opening),
                            step=100.0,
                            format="%.2f",
                            key=f"bal_{acc_id}"
                        )

                    save_btn = st.form_submit_button("💾 Save Changes", type="primary")

                    if save_btn:
                        if not new_name:
                            st.error("Account name cannot be empty")
                        else:
                            updated = update_account(
                                conn,
                                acc_id,
                                name=new_name,
                                institution=(new_inst or None),
                                currency=new_currency,
                                type=new_type,
                                opening_balance=new_balance
                            )
                            if updated:
                                st.success(f"✅ Account '{new_name}' updated successfully!")
                                st.rerun()
                            else:
                                st.warning("No changes made")

                st.divider()
                if st.button("🗑️ Delete Account", key=f"del_{acc_id}", type="secondary"):
                    st.session_state[f"delete_account_{acc_id}"] = True

                if st.session_state.get(f"delete_account_{acc_id}", False):
                    confirm_delete_dialog(acc_id, acc_name, txn_count)
