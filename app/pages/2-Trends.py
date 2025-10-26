from pathlib import Path
import pandas as pd
import streamlit as st

from ledger.db import bootstrap
from ledger.analytics import monthly_spend_series, trend_summary

st.title("📈 Trends (Non-parametric)")

DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")
conn = bootstrap(DB_PATH)

col1, col2, col3 = st.columns(3)
with col1:
    base = st.selectbox("Base currency", ["KRW","USD"], index=0, help="FX 캐시 기준으로 환산")
with col2:
    months = st.slider("Lookback (months)", min_value=6, max_value=48, value=18, step=1)
with col3:
    # 최근 사용 카테고리 후보 추출
    # 간단히 전체 시계열에서 조회된 카테고리 목록을 뽑기보다 사용자 입력형으로 유지
    category = st.text_input("Filter by category (optional)", value="")

# 시계열 생성
series = monthly_spend_series(conn, base=base, months=months, category=(category or None))
summ = trend_summary(conn, base=base, months=months, category=(category or None))

# 라벨링 로직
def label_trend(summ):
    tau, p, slope = summ.get("tau"), summ.get("p"), summ.get("slope")
    if tau is None or p is None or slope is None:
        return "Insufficient data (n<3)"
    signif = (p < 0.05)
    if signif and slope > 0:
        return "📈 Increasing (significant)"
    if signif and slope < 0:
        return "📉 Decreasing (significant)"
    if not signif and slope > 0:
        return "↗ Weak increase (ns)"
    if not signif and slope < 0:
        return "↘ Weak decrease (ns)"
    return "— Flat"

colA, colB, colC, colD = st.columns(4)
colA.metric("Last month", f"{(summ['last'] or 0.0):,.0f} {base}")
colB.metric("Avg (window)", f"{(summ['mean'] or 0.0):,.0f} {base}")
colC.metric("τ (MK)", "—" if summ["tau"] is None else f"{summ['tau']:.2f}")
colD.metric("p-value", "—" if summ["p"] is None else f"{summ['p']:.3f}")

slope_val = summ.get("slope")
slope_text = "—" if slope_val is None else f"{slope_val:.0f} {base}/mo"
st.info(f"Trend: **{label_trend(summ)}**  •  Theil–Sen slope ≈ **{slope_text}**")

st.subheader("Monthly spend (base)")
# 시각화용 DataFrame
df = pd.DataFrame({"month": series.index, f"spend_{base}": series.values})
st.line_chart(df.set_index("month"))

st.caption(
    "Mann–Kendall: τ는 순위 기반 상관계수(−1~+1), p<0.05면 통계적으로 유의한 추세.\n"
    "Theil–Sen: 이상치에 강인한 중앙 기울기(월당 금액 변화량)."
)
