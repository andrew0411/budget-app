# app/pages/7-Rules.py
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from ledger.db import (
    bootstrap,
    add_rule, list_rules, update_rule, delete_rule,
    list_transactions_joined, update_transaction
)
from ledger.rules import apply_category_rules

st.title("🧩 Category Rules")

# 모든 페이지가 루트 db.sqlite3를 보도록 고정
DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

st.caption("priority가 낮을수록 먼저 평가합니다(ASC). match_type: contains | regex")

# ──────────────────────────────────────────────────────────────────────────────
# Create (추가)
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("Add Rule")

with st.form("add_rule"):
    col1, col2, col3, col4, col5 = st.columns([2,1,2,1,1])
    with col1:
        pattern = st.text_input("pattern (키워드 또는 정규식)", value="", help="예: 'starbucks' 또는 'coffee|☕'")
    with col2:
        mtype = st.selectbox("match_type", ["contains", "regex"], index=0)
    with col3:
        category = st.text_input("category", value="Coffee")
    with col4:
        inst = st.text_input("institution(선택)", value="", help="이 값이 채워지면 해당 기관일 때만 매치")
    with col5:
        prio = st.number_input("priority", value=100, step=1, help="작을수록 먼저 평가")
    enabled = st.checkbox("enabled", value=True)
    submitted = st.form_submit_button("Create")
    if submitted:
        if not pattern or not category:
            st.error("pattern과 category는 필수입니다.")
        else:
            add_rule(conn, pattern=pattern, category=category, match_type=mtype,
                     institution=(inst or None), priority=int(prio), enabled=bool(enabled))
            st.success("Rule created.")
            st.experimental_rerun()

# ──────────────────────────────────────────────────────────────────────────────
# List / Edit (수정)
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("Rules (edit inline)")

rows = list_rules(conn, include_disabled=True)
df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

if df.empty:
    st.info("No rules yet. 상단에서 새 룰을 추가하세요.")
else:
    show_cols = ["id","pattern","match_type","category","institution","priority","enabled"]
    df = df[show_cols].copy()
    edited = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        key="rules_editor",
        column_config={
            "match_type": st.column_config.SelectboxColumn("match_type", options=["contains","regex"]),
            "enabled": st.column_config.CheckboxColumn("enabled"),
            "priority": st.column_config.NumberColumn("priority", step=1),
        },
        num_rows="fixed",
    )

    colA, colB = st.columns([1,1])
    with colA:
        if st.button("Apply changes"):
            changed = 0
            for _, row in edited.iterrows():
                orig = df[df["id"]==row["id"]].iloc[0]
                fields = {}
                for c in ["pattern","match_type","category","institution","priority","enabled"]:
                    if str(row[c]) != str(orig[c]):
                        fields[c] = (None if (pd.isna(row[c]) or row[c]=="") else row[c])
                if fields:
                    changed += update_rule(conn, int(row["id"]), **fields)
            st.success(f"Updated {changed} rule(s)." if changed else "No changes.")
            st.experimental_rerun()

    with colB:
        del_id = st.selectbox("Delete rule id", options=list(edited["id"]), index=0)
        if st.button("Delete selected rule"):
            delete_rule(conn, int(del_id))
            st.success(f"Deleted rule {del_id}.")
            st.experimental_rerun()

# ──────────────────────────────────────────────────────────────────────────────
# Test console (테스트)
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("Test console")

col1, col2 = st.columns([2,2])
with col1:
    payee = st.text_input("payee (예: 'STARBUCKS GANGNAM')", value="")
with col2:
    inst = st.text_input("institution (예: 'Chase' 또는 'KB')", value="")
if st.button("Test rule match"):
    cat = apply_category_rules(conn, payee=payee or None, institution=inst or None)
    if cat:
        st.success(f"Matched category: **{cat}**")
    else:
        st.info("No rule matched.")

# ──────────────────────────────────────────────────────────────────────────────
# Bulk Apply (일괄 적용)
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("Bulk apply rules to transactions")

with st.expander("설명 및 실행", expanded=False):
    st.markdown(
        "- **목적**: 기간 내 거래에 룰을 재적용하여 `category`를 업데이트합니다.\n"
        "- **주의**: 삭제는 아니지만 **카테고리 값이 변경**될 수 있습니다."
    )
    colx, coly, colz = st.columns(3)
    with colx:
        days = st.slider("최근 N일", min_value=7, max_value=180, value=60, step=1)
    with coly:
        include_deleted = st.checkbox("Include deleted", value=False)
    with colz:
        limit = st.selectbox("Limit", [200,500,1000,2000], index=1)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(days))
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    st.caption(f"적용 범위(UTC): {start_iso} ~ {end_iso}")

    if st.button("Apply rules now"):
        rows = list_transactions_joined(conn,
                                        start_iso=start_iso,
                                        end_iso=end_iso,
                                        include_deleted=include_deleted,
                                        limit=int(limit))
        if not rows:
            st.info("해당 범위에 거래가 없습니다.")
        else:
            updated = 0
            for r in rows:
                new_cat = apply_category_rules(conn, payee=r["payee"], institution=r["institution"])
                if new_cat and new_cat != r["category"]:
                    updated += update_transaction(conn, int(r["id"]), category=new_cat)
            st.success(f"Rules applied to {updated} transaction(s).")
