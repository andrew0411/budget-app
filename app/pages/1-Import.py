from pathlib import Path

import pandas as pd
import streamlit as st

from ledger.db import bootstrap, ensure_default_accounts, add_transaction
from ledger.importer import (
    dataframe_from_csv,
    Mapping,
    Defaults,
    map_df_to_txns,
    mark_duplicates,
)

# 페이지 파일에서는 set_page_config를 다시 호출하지 않는 것을 권장
st.title("📥 CSV Import")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

# 🔹 Simple Mode: 기본 계정 자동 보장 + 통화별 라우팅
default_acc = ensure_default_accounts(conn, currencies=("KRW", "USD"))  # {"KRW": id1, "USD": id2}

uploaded = st.file_uploader("CSV 파일 업로드", type=["csv"])
if not uploaded:
    st.info("CSV를 업로드하면 50행 미리보기를 보여줍니다.")
    st.stop()

try:
    df = dataframe_from_csv(uploaded)
except Exception as e:
    st.error(f"CSV 읽기 실패: {e}")
    st.stop()

st.subheader("미리보기 (상위 50행)")
st.dataframe(df.head(50))

# 컬럼 매핑
cols = ["— (skip)"] + list(df.columns)

def pick(label, required=False):
    return st.selectbox(label + (" *" if required else ""), cols, index=1 if required else 0)

st.subheader("컬럼 매핑")
date_col = pick("날짜 컬럼", required=True)
amount_col = pick("금액 컬럼", required=True)
currency_col = pick("통화 컬럼")   # 없으면 기본 통화 사용
payee_col = pick("가맹점/메모")
category_col = pick("카테고리")
notes_col = pick("비고/노트")

# 기본 통화는 KRW로 두되, 통화 컬럼 있으면 해당 값 사용 (행마다 KRW/USD 라우팅)
defaults = Defaults(
    currency="KRW",
    category="Uncategorized",
    direction=st.radio("지출/수입 방향(기본 auto: 음수=지출, 양수=수입)", ["auto", "debit", "credit"], index=0),
)

mapping = Mapping(
    date=date_col,
    amount=amount_col,
    currency=None if currency_col.startswith("—") else currency_col,
    payee=None if payee_col.startswith("—") else payee_col,
    category=None if category_col.startswith("—") else category_col,
    notes=None if notes_col.startswith("—") else notes_col,
)

if st.button("Dry-run (중복 감지 포함)"):
    with st.spinner("변환 중…"):
        txns = map_df_to_txns(df, mapping, defaults)
        if not txns:
            st.error("매핑 결과가 비었습니다. 날짜/금액 컬럼을 다시 확인해주세요.")
            st.stop()

        # 각 행의 통화에 맞춰 해당 기본 계정 기준으로 중복 검사
        marked_all = []
        for t in txns:
            cur = (t["currency"] or "KRW").upper()
            account_id = default_acc.get(cur) or default_acc.get("KRW")
            marked = mark_duplicates(conn, account_id, [t])
            marked_all.extend(marked)

    st.success(f"총 {len(marked_all)}건 변환됨.")
    st.write("중복(duplicate)이 True인 행은 기본적으로 삽입하지 않습니다.")
    st.dataframe(pd.DataFrame(marked_all).head(100))

    insert_mode = st.radio("삽입 모드", ["중복 제외(권장)", "중복도 강제 삽입"])
    if st.button("DB에 삽입"):
        ins = 0
        for t in marked_all:
            if insert_mode == "중복 제외(권장)" and t["duplicate"]:
                continue
            cur = (t["currency"] or "KRW").upper()
            account_id = default_acc.get(cur) or default_acc.get("KRW")
            add_transaction(
                conn,
                date_utc=t["date_utc"],
                amount=t["amount"],
                currency=cur,
                category=t["category"],
                account_id=account_id,
                direction=t["direction"],
                notes=t.get("notes"),
                payee=t.get("payee"),
            )
            ins += 1
        st.success(f"삽입 완료: {ins}건")
        st.toast("삽입이 끝났습니다. Main 페이지에서 카운트를 확인하세요.", icon="✅")
