from pathlib import Path
from datetime import datetime, timezone, timedelta
from app.ui import inject_css
import streamlit as st

from ledger.db import (
    bootstrap,
    count_rows,
    add_account,
    add_transaction,
    ensure_default_accounts,
    get_latest_fx,
    upsert_fx_cache_many,   # 🔹 FX upsert 헬퍼
)
from ledger.fx.fred import fetch_dexkous, SOURCE_LABEL
from ledger.backup import ensure_daily_backup, create_backup, list_backups

st.set_page_config(page_title="Budget App", page_icon="💸", layout="wide")

st.title("💸 Budget App")
inject_css()
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

    st.divider()

    # 🔹 FX(USD→KRW) 섹션: 최신값 표시 + FRED에서 최근 14일 가져오기
    with st.expander("FX (USD→KRW)", expanded=True):
        latest = get_latest_fx(conn, "USD", "KRW")
        if latest:
            st.info(
                f"🇺🇸1 USD = 🇰🇷 {latest['rate']:,.2f} KRW  • As of {latest['date_utc']}  • {latest['source']}"
            )
        else:
            st.warning("환율 데이터가 없습니다. 아래 버튼으로 불러오세요.")

        # 외부 API 호출 목적/입력값 공지
        st.caption("외부 호출 목적: FRED DEXKOUS에서 최근 일자 환율 수집. 입력값: start/end(최근 14일), FRED_API_KEY")

        if st.button("Fetch latest from FRED"):
            try:
                end = datetime.now(timezone.utc).date()
                start = end - timedelta(days=14)
                observations = fetch_dexkous(start, end)  # 🔸 외부 API 호출
                rows = [(o["date"], "USD", "KRW", o["rate"], SOURCE_LABEL) for o in observations]
                n = upsert_fx_cache_many(conn, rows)
                st.success(f"갱신 완료: {n}건 upsert")

                # 갱신 후 배너 재표시
                latest = get_latest_fx(conn, "USD", "KRW")
                if latest:
                    st.info(
                        f"🇺🇸1 USD = 🇰🇷 {latest['rate']:,.2f} KRW  • As of {latest['date_utc']}  • {latest['source']}"
                    )
            except Exception as e:
                st.error(f"갱신 실패: {e}")

    st.divider()

    # 🔹 Backups 섹션: 일일 자동 백업 + 수동 백업 + 최근 백업 목록
    with st.expander("Backups", expanded=False):
        try:
            created_today = ensure_daily_backup(DB_PATH)  # 하루 1회 자동
            if created_today:
                st.success("일일 자동 백업 생성 완료.")
        except Exception as e:
            st.warning(f"자동 백업 건너뜀: {e}")

        if st.button("Create backup now"):
            try:
                dest = create_backup(DB_PATH)
                st.success(f"백업 생성: {dest.name}")
            except Exception as e:
                st.error(f"백업 실패: {e}")

        st.caption("최근 백업 (최대 5개)")
        backs = list_backups(limit=5)
        if backs:
            for b in backs:
                st.write("• ", b.name)
        else:
            st.write("백업 없음")

# --- 상단 카드들 ---
c1, c2, c3 = st.columns(3)
c1.metric("Total Assets (base)", "—", help="KRW or USD after data & FX")
c2.metric("Month-to-date Spend", "—")

# 🔹 최신 환율 텍스트(사이드바에 표시된 최신값을 카드에도 축약)
latest_for_metric = get_latest_fx(conn, "USD", "KRW") if "conn" in locals() else None
fx_text = f"{latest_for_metric['rate']:,.2f} KRW" if latest_for_metric else "—"
c3.metric("FX (USD→KRW)", fx_text, help="FRED DEXKOUS as-of appears in sidebar")

st.success("Scaffold OK. CSV import, FX provider wired, backups added. Next: analytics/charts.")
