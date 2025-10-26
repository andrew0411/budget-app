# app/pages/6_Transactions.py
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from ledger.db import bootstrap, list_transactions_joined, update_transaction, soft_delete_transaction

st.title("🧾 Transactions — Edit & Delete")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

col1, col2, col3 = st.columns(3)
with col1:
    days = st.slider("최근 N일", min_value=7, max_value=120, value=60, step=1)
with col2:
    include_deleted = st.checkbox("Show deleted", value=False)
with col3:
    limit = st.selectbox("Limit", [100,200,300,500], index=2)

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

df = pd.DataFrame([dict(r) for r in rows])

# 편집 허용 컬럼만 열어두기
editable_cols = ["category","payee","notes","direction"]
df["delete"] = False  # 삭제 선택용

st.caption("Tip: 여러 행을 수정한 뒤 'Apply changes'를 누르세요. 삭제는 체크 후 'Delete selected'.")
edited = st.data_editor(
    df[["id","date_utc","amount","currency","account_name","institution","direction","category","payee","notes","delete"]],
    hide_index=True,
    disabled=["id","date_utc","amount","currency","account_name","institution"],
    key="txn_editor",
)

colA, colB = st.columns([1,1])
with colA:
    if st.button("Apply changes"):
        changed = 0
        for _, row in edited.iterrows():
            orig = df[df["id"]==row["id"]].iloc[0]
            fields = {}
            for c in editable_cols:
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
