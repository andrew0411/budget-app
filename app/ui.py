# app/ui.py
from __future__ import annotations
import streamlit as st
import altair as alt
import pandas as pd

# ── Light palette (기본) ─────────────────────────────────────────────────────
PALETTE = {
    "mint":   "#89B6A5",
    "lilac":  "#C1BBD3",
    "peach":  "#F7C6AF",
    "sky":    "#A6D0E4",
    "lemon":  "#F5E97B",
    "rose":   "#F2A0A1",
    "ink":    "#2B2D42",
    "bg":     "#F7F7FB",
    "card":   "#FFFFFF",
    "muted":  "#6B7280",
}

# ── Dark mode state helpers ──────────────────────────────────────────────────
def get_dark_mode() -> bool:
    return bool(st.session_state.get("_ui_dark", False))

def set_dark_mode(flag: bool) -> None:
    st.session_state["_ui_dark"] = bool(flag)

# ── Money formatter (숫자/라벨 일관성) ───────────────────────────────────────
def fmt_money(v: float | None, cur: str) -> str:
    """금액을 통화와 함께 일관되게 포맷."""
    if v is None:
        return f"— {cur}"
    # 1,000 이상은 0자리, 그 미만은 2자리 소수
    if abs(v) >= 1000:
        return f"{v:,.0f} {cur}"
    return f"{v:,.2f} {cur}"

# ── 전역 CSS 주입 (Light/Dark 지원) ─────────────────────────────────────────
def inject_css(pad_top: str = "2.25rem", sticky_offset: str = "56px") -> None:
    """
    UI 전역 CSS 주입.
    - pad_top: 페이지 컨텐츠 상단 여백(제목 잘림 방지)
    - sticky_offset: DataFrame thead sticky offset
    """
    dark = get_dark_mode()
    if dark:
        palette = {
            "bg": "#0f1115", "card": "#161a23", "ink": "#E6E6E6", "muted": "#A0AEC0",
            "mint": "#7BC3AE", "lilac": "#AFA5D9", "peach": "#F2B79C", "sky": "#86BFD8",
            "lemon": "#E9DD6F", "rose": "#EE8E90",
        }
    else:
        palette = {
            "bg": PALETTE["bg"], "card": PALETTE["card"], "ink": PALETTE["ink"], "muted": PALETTE["muted"],
            "mint": PALETTE["mint"], "lilac": PALETTE["lilac"], "peach": PALETTE["peach"],
            "sky": PALETTE["sky"], "lemon": PALETTE["lemon"], "rose": PALETTE["rose"],
        }

    st.markdown(
        f"""
<style>
:root {{
  --pl-pad-top: {pad_top};
  --pl-sticky-offset: {sticky_offset};
  --pl-bg: {palette["bg"]};
  --pl-card: {palette["card"]};
  --pl-ink: {palette["ink"]};
  --pl-muted: {palette["muted"]};
  --pl-mint: {palette["mint"]};
  --pl-lilac: {palette["lilac"]};
  --pl-peach: {palette["peach"]};
  --pl-sky: {palette["sky"]};
  --pl-lemon: {palette["lemon"]};
  --pl-rose: {palette["rose"]};
}}

/* 배경/텍스트 기본 색 적용 */
html, body, .block-container {{
  background: var(--pl-bg) !important;
  color: var(--pl-ink) !important;
}}
/* 컨테이너 여백: 제목 상단 잘림 방지 */
.block-container {{ padding-top: var(--pl-pad-top); }}

/* 헤딩 가독성 & 잘림 방지 */
h1, h2, h3 {{
  letter-spacing: .2px;
  line-height: 1.28;
  margin-top: .25rem;
  overflow: visible;
}}
p, span, li, label {{ font-size: 0.95rem; }}

/* 메트릭 카드 */
.pl-card {{
  background: var(--pl-card);
  border: 1px solid rgba(0,0,0,.05);
  border-radius: 16px;
  padding: .9rem 1rem;
  box-shadow: 0 3px 10px rgba(0,0,0,.04);
}}
.pl-card .pl-label {{ color: var(--pl-muted); font-size: .9rem; }}
.pl-card .pl-value {{ font-weight: 700; font-size: 1.35rem; color: var(--pl-ink); }}
.pl-card .pl-sub   {{ color: var(--pl-muted); font-size: .85rem; }}

/* 칩/배지 */
.pl-chip {{
  display:inline-block; padding:.2rem .6rem; border-radius:999px;
  background: var(--pl-bg); border:1px solid rgba(0,0,0,.06);
  color: var(--pl-ink); font-size:.8rem; margin-right:.3rem;
}}
.pl-chip.info   {{ background: #EEF7F4; border-color: #DDEEE8; color:#245E54; }}
.pl-chip.warn   {{ background: #FFF7E6; border-color: #FFE3A3; color:#8A5A00; }}
.pl-chip.danger {{ background: #FDECEC; border-color: #F8CACA; color:#6F1D1D; }}

/* 이모지: 과도한 상단 이동 제거(잘림 방지) */
h1 .emoji, h2 .emoji {{
  font-size: 1.2em;
  vertical-align: baseline;
}}

/* 표: 줄무늬 & 헤더 고정(제목 가림 방지 offset 사용) */
[data-testid="stDataFrame"] tbody tr:nth-child(odd) {{ background: rgba(0,0,0,.03); }}
[data-testid="stDataFrame"] thead {{
  position: sticky;
  top: var(--pl-sticky-offset);
  z-index: 1;
}}
</style>
""",
        unsafe_allow_html=True,
    )

# ── 카드/배지 컴포넌트 ───────────────────────────────────────────────────────
def metric_card(label: str, value: str, sub: str | None = None) -> None:
    st.markdown(
        f"""
<div class="pl-card">
  <div class="pl-label">{label}</div>
  <div class="pl-value">{value}</div>
  {"<div class='pl-sub'>" + sub + "</div>" if sub else ""}
</div>
""",
        unsafe_allow_html=True,
    )

def chip(text: str, tone: str = "info") -> None:
    tone = tone if tone in {"info","warn","danger"} else "info"
    st.markdown(f"""<span class="pl-chip {tone}">{text}</span>""", unsafe_allow_html=True)

# ── 차트 헬퍼(Altair, title=None 안전) ───────────────────────────────────────
def area_chart(df: pd.DataFrame, x: str, y: str, title: str | None = None):
    chart = alt.Chart(df)
    if title:
        chart = chart.properties(title=title)
    chart = (
        chart.mark_area(opacity=0.5, line={"color": PALETTE["mint"], "width": 2})
             .encode(
                 x=alt.X(x, sort=None, axis=alt.Axis(labelAngle=0)),
                 y=alt.Y(y, stack=None),
                 tooltip=[x, y],
             )
             .properties(height=260)
    )
    return st.altair_chart(chart, use_container_width=True)

def bar_chart(df: pd.DataFrame, x: str, y: str, title: str | None = None):
    chart = alt.Chart(df)
    if title:
        chart = chart.properties(title=title)
    chart = (
        chart.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
             .encode(
                 x=alt.X(x, sort='-y'),
                 y=alt.Y(y),
                 tooltip=[x, y],
                 color=alt.value(PALETTE["sky"]),
             )
             .properties(height=280)
    )
    return st.altair_chart(chart, use_container_width=True)
