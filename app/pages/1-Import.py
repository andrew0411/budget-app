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
    resolve_account_id,   # ✅ 계정 결정(자동 생성 포함)
)

# 페이지 파일에서는 set_page_config를 다시 호출하지 않는 것을 권장
st.title("📥 CSV Import")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

# 🔹 Simple Mode 기본: 통화별 기본 계정 (최종 fallback 용)
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

# --- 컬럼 매핑 ---
cols = ["— (skip)"] + list(df.columns)

def pick(label, required=False):
    return st.selectbox(label + (" *" if required else ""), cols, index=1 if required else 0)

st.subheader("컬럼 매핑")
date_col = pick("날짜 컬럼", required=True)
amount_col = pick("금액 컬럼", required=True)
currency_col = pick("통화 컬럼")                    # 없으면 기본 통화 사용
payee_col = pick("가맹점/메모")
category_col = pick("카테고리")
notes_col = pick("비고/노트")

# ✅ 추가: 계정/기관 컬럼 매핑 (있으면 사용)
account_col = pick("계정명 컬럼")                   # 예: 'Chase Sapphire', '국민카드' 등
institution_col = pick("기관(은행/카드) 컬럼")       # 예: 'Chase', 'KB', 'UWCU' 등

# 기본 통화는 KRW로 두되, 통화 컬럼 있으면 해당 값 사용
defaults = Defaults(
    currency="KRW",
    category="Uncategorized",
    direction=st.radio("지출/수입 방향(기본 auto: 음수=지출, 양수=수입)", ["auto", "debit", "credit"], index=0),
)

# ✅ 없는 계정 자동 생성 옵션
auto_create = st.checkbox("없는 계정은 자동 생성", value=True,
                          help="계정명/기관/Payee 힌트로 찾지 못하면 새 계정을 생성합니다. (type=card, opening_balance=0)")

mapping = Mapping(
    date=date_col,
    amount=amount_col,
    currency=None if currency_col.startswith("—") else currency_col,
    payee=None if payee_col.startswith("—") else payee_col,
    category=None if category_col.startswith("—") else category_col,
    notes=None if notes_col.startswith("—") else notes_col,
    account=None if account_col.startswith("—") else account_col,              # ✅ 추가
    institution=None if institution_col.startswith("—") else institution_col,  # ✅ 추가
)

if st.button("Dry-run (계정 매핑+중복 감지)"):
    with st.spinner("변환/라우팅 중…"):
        txns = map_df_to_txns(df, mapping, defaults)
        if not txns:
            st.error("매핑 결과가 비었습니다. 날짜/금액 컬럼을 다시 확인해주세요.")
            st.stop()

        # 행별 계정 라우팅 + 계정 단위 중복 감지
        marked_all = []
        for i, t in enumerate(txns):
            # 통화 결정 (없으면 기본통화)
            cur = (t.get("currency") or defaults.currency).upper()

            # 원본 DF에서 계정/기관 힌트 추출
            acct_hint = None
            inst_hint = None
            if mapping.account and (mapping.account in df.columns):
                v = df.iloc[i][mapping.account]
                acct_hint = None if pd.isna(v) else str(v)
            if mapping.institution and (mapping.institution in df.columns):
                v = df.iloc[i][mapping.institution]
                inst_hint = None if pd.isna(v) else str(v)

            # ✅ 계정 결정(없으면 기관/Payee 추정 → 자동 생성 옵션 반영)
            account_id = resolve_account_id(
                conn,
                currency=cur,
                account_name=acct_hint,
                institution=inst_hint,
                payee=t.get("payee"),
                defaults_by_currency=default_acc,
                auto_create=auto_create,
            )

            # ✅ 계정 단위로 중복 감지
            flagged = mark_duplicates(conn, account_id, [t])[0]
            flagged["account_id"] = account_id
            marked_all.append(flagged)

    st.success(f"총 {len(marked_all)}건 변환됨. (계정 라우팅 및 중복 감지 완료)")
    st.write("중복(duplicate)이 True인 행은 기본적으로 삽입하지 않습니다.")
    preview_cols = ["date_utc", "amount", "currency", "category", "payee", "direction", "account_id", "duplicate"]
    st.dataframe(pd.DataFrame(marked_all)[preview_cols].head(100))

    insert_mode = st.radio("삽입 모드", ["중복 제외(권장)", "중복도 강제 삽입"])
    if st.button("DB에 삽입"):
        ins = 0
        for t in marked_all:
            if insert_mode == "중복 제외(권장)" and t["duplicate"]:
                continue
            add_transaction(
                conn,
                date_utc=t["date_utc"],
                amount=t["amount"],
                currency=t["currency"],     # 행의 실제 통화 유지
                category=t["category"],
                account_id=t["account_id"], # ✅ 통화가 아니라 '계정'으로 라우팅
                direction=t["direction"],
                notes=t.get("notes"),
                payee=t.get("payee"),
            )
            ins += 1
        st.success(f"삽입 완료: {ins}건")
        st.toast("삽입이 끝났습니다. Dashboard/Transactions에서 확인하세요.", icon="✅")
