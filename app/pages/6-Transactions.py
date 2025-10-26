from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from ledger.db import (
    bootstrap, list_transactions_joined, update_transaction, soft_delete_transaction,
    get_accounts  # ✅ get_accounts_full 대신 사용
)
from ledger.rules import apply_category_rules  # 선택: 룰 재적용 버튼용

st.title("🧾 Transactions — Edit & Delete")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

col1, col2, col3 = st.columns(3)
with col1:
    days = st.slider("최근 N일", min_value=7, max_value=180, value=60, step=1)
with col2:
    include_deleted = st.checkbox("Show deleted", value=False)
with col3:
    limit = st.selectbox("Limit", [100, 200, 300, 500], index=2)

end = datetime.now(timezone.utc)
start = end - timedelta(days=days)
rows = list_transactions_joined(conn,
                                start_iso=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                end_iso=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                include_deleted=include_deleted,
                                limit=int(limit))

if not rows:
    st.info("No transactions in range.")
    st.stop()

df = pd.DataFrame([dict(r) for r in rows])  # dict로 변환하여 안전 조작

# 계정 셀렉트 옵션 구성 (get_accounts → dict 변환 후 안전 라벨)
acc_rows = [dict(r) for r in get_accounts(conn)]
acc_options = {}
for a in acc_rows:
    aid = int(a["id"])
    name = a.get("name") or ""
    inst = a.get("institution") or ""
    cur = str(a.get("currency", "")).upper()
    typ = a.get("type") or ""
    label = f"{aid} — {name} ({inst}) [{cur}/{typ}]"
    acc_options[label] = aid

# id → label 역맵
id2label = {v: k for k, v in acc_options.items()}

# 편집용 보조 컬럼
df["delete"] = False
df["undelete"] = False
df["account_label"] = df["account_id"].map(lambda x: id2label.get(int(x), str(x)))

st.caption("Tip: Account 드롭다운으로 계정 변경, Delete/Undelete 체크 후 각 버튼으로 일괄 적용.")

edited = st.data_editor(
    df[["id", "date_utc", "amount", "currency", "account_label", "institution", "direction", "category", "payee", "notes", "is_deleted", "delete", "undelete"]],
    column_config={
        "account_label": st.column_config.SelectboxColumn(
            "Account",
            options=list(acc_options.keys()),
            help="계정을 변경하면 account_id가 갱신됩니다.",
        ),
        "is_deleted": st.column_config.CheckboxColumn("Deleted", disabled=True),
        "delete": st.column_config.CheckboxColumn("Delete?"),
        "undelete": st.column_config.CheckboxColumn("Undelete?"),
    },
    hide_index=True,
    disabled=["id", "date_utc", "amount", "currency", "institution", "is_deleted"],
    use_container_width=True,
    key="txn_editor_v2",
)

colA, colB, colC, colD = st.columns(4)

with colA:
    if st.button("Apply changes"):
        changed = 0
        for _, row in edited.iterrows():
            orig = df[df["id"] == row["id"]].iloc[0]
            fields = {}
            # 계정 변경
            if row["account_label"] != orig["account_label"]:
                fields["account_id"] = acc_options[row["account_label"]]
            # 텍스트 필드
            for c in ["direction", "category", "payee", "notes"]:
                if str(row[c]) != str(orig[c]):
                    fields[c] = row[c] if pd.notna(row[c]) else None
            if fields:
                changed += update_transaction(conn, int(row["id"]), **fields)
        st.success(f"Updated {changed} row(s)." if changed else "No changes.")
        st.experimental_rerun()

with colB:
    if st.button("Delete selected"):
        deleted = 0
        for _, row in edited.iterrows():
            if bool(row.get("delete")) and not bool(row.get("is_deleted", False)):
                deleted += soft_delete_transaction(conn, int(row["id"]), True)
        st.success(f"Deleted {deleted} row(s)." if deleted else "No selection.")
        st.experimental_rerun()

with colC:
    if st.button("Undelete selected"):
        restored = 0
        for _, row in edited.iterrows():
            if bool(row.get("undelete")) and bool(row.get("is_deleted", False)):
                restored += soft_delete_transaction(conn, int(row["id"]), False)
        st.success(f"Restored {restored} row(s)." if restored else "No selection.")
        st.experimental_rerun()

with colD:
    if st.button("Re-apply rules to selected"):
        updated = 0
        for _, row in edited.iterrows():
            if bool(row.get("delete")) or bool(row.get("undelete")):
                continue
            new_cat = apply_category_rules(conn, payee=row.get("payee"), institution=row.get("institution"))
            if new_cat and new_cat != row.get("category"):
                updated += update_transaction(conn, int(row["id"]), category=new_cat)
        st.success(f"Rules applied to {updated} row(s)." if updated else "No changes.")
        st.experimental_rerun()
