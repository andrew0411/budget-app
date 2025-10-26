# app/pages/5_BankBreakdown.py
from pathlib import Path
from datetime import datetime, timedelta, timezone

import streamlit as st
import pandas as pd

from app.ui import inject_css, bar_chart, fmt_money
from ledger.db import bootstrap
from ledger.analytics import spend_by_institution

st.title("🏦 Bank / Card Breakdown")
inject_css()

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

col1, col2, col3 = st.columns(3)
with col1:
    base = st.selectbox("기준 통화", ["KRW", "USD"], index=0)
with col2:
    months = st.slider("최근 N개월", 1, 24, 6, 1)
with col3:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=months * 31)
    st.write(f"{start.date()} ~ {end.date()}")

start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
end_iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")

df = spend_by_institution(conn, base, start_iso, end_iso)
if df.empty:
    st.info("데이터가 없습니다. 몇 건 입력·임포트한 뒤 다시 시도하세요.")
else:
    st.subheader("기관별 지출 합계")
    # 차트: 숫자 그대로 사용
    bar_chart(df.rename(columns={"institution": "Institution", "amount_base": "Amount"})[["Institution", "Amount"]],
              x="Institution", y="Amount")

    # 표: 금액은 포맷 적용해서 별도 컬럼으로 표시
    df_show = df.copy()
    df_show[f"amount_{base}"] = df_show["amount_base"].map(lambda x: fmt_money(float(x or 0.0), base))
    st.dataframe(df_show[["institution", f"amount_{base}", "count"]]
                 .rename(columns={"institution": "Institution", f"amount_{base}": f"Amount ({base})", "count": "Count"}),
                 use_container_width=True)
