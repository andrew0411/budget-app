# app/ui.py
from __future__ import annotations
import streamlit as st
import altair as alt
import pandas as pd
from typing import Optional, Union

Number = Union[int, float]

# ── Pastel palette (consistent colors) ────────────────────────────────────────
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

# ── Global CSS injection ─────────────────────────────────────────────────────
def inject_css(
    pad_top: str = "2.25rem",
    sticky_offset: str = "56px",
    max_width: str = "1600px",  # widen the content area a bit more
) -> None:
    """
    Inject global CSS.
    - pad_top: top padding of the page content to prevent title clipping
    - sticky_offset: sticky header offset for dataframes
    - max_width: increase page content width (e.g., '1500px', '85vw')
    """
    st.markdown(
        f"""
<style>
:root {{
  --pl-pad-top: {pad_top};
  --pl-sticky-offset: {sticky_offset};
  --pl-max-width: {max_width};
  --pl-mint:   {PALETTE["mint"]};
  --pl-lilac:  {PALETTE["lilac"]};
  --pl-peach:  {PALETTE["peach"]};
  --pl-sky:    {PALETTE["sky"]};
  --pl-lemon:  {PALETTE["lemon"]};
  --pl-rose:   {PALETTE["rose"]};
  --pl-ink:    {PALETTE["ink"]};
  --pl-bg:     {PALETTE["bg"]};
  --pl-card:   {PALETTE["card"]};
  --pl-muted:  {PALETTE["muted"]};
}}

/* Widen main content area and add top padding (prevent title clipping) */
.block-container {{
  padding-top: var(--pl-pad-top);
  max-width: var(--pl-max-width);
}}

/* Headings readability & prevent clipping */
h1, h2, h3 {{
  letter-spacing: .2px;
  line-height: 1.28;
  margin-top: .25rem;
  overflow: visible;
}}
p, span, li, label {{ font-size: 0.95rem; }}

/* Cards */
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

/* Chips */
.pl-chip {{
  display:inline-block; padding:.2rem .6rem; border-radius:999px;
  background: var(--pl-bg); border:1px solid rgba(0,0,0,.06);
  color: var(--pl-ink); font-size:.8rem; margin-right:.3rem;
}}
.pl-chip.info   {{ background: #EEF7F4; border-color: #DDEEE8; color:#245E54; }}
.pl-chip.warn   {{ background: #FFF7E6; border-color: #FFE3A3; color:#8A5A00; }}
.pl-chip.danger {{ background: #FDECEC; border-color: #F8CACA; color:#6F1D1D; }}

/* Emoji alignment (prevent excessive vertical shift) */
h1 .emoji, h2 .emoji {{
  font-size: 1.2em;
  vertical-align: baseline;
}}

/* Dataframe: zebra rows & sticky header */
[data-testid="stDataFrame"] tbody tr:nth-child(odd) {{ background: rgba(0,0,0,.02); }}
[data-testid="stDataFrame"] thead {{
  position: sticky;
  top: var(--pl-sticky-offset);
  z-index: 1;
}}

/* ────────────────────────────────────────────────────────────────────────────
   Hide "Press Enter to submit form" helper across Streamlit versions.
   We scope to the submitter container to avoid silencing other announcements.
   ──────────────────────────────────────────────────────────────────────────── */
/* Older & common test id */
div[data-testid="stFormSubmitterMessage"] {{ display:none !important; opacity:0 !important; height:0 !important; margin:0 !important; padding:0 !important; overflow:hidden !important; }}

/* Newer structure: message rendered as a status node inside the submitter */
div[data-testid="stFormSubmitter"] div[role="status"] {{ 
  display:none !important; opacity:0 !important; height:0 !important; margin:0 !important; padding:0 !important; overflow:hidden !important;
}}

/* Fallback: any aria-live polite node directly under the submitter */
div[data-testid="stFormSubmitter"] [aria-live="polite"] {{
  display:none !important; opacity:0 !important; height:0 !important; margin:0 !important; padding:0 !important; overflow:hidden !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )

# ── Display components ───────────────────────────────────────────────────────
def metric_card(label: str, value: str, sub: Optional[str] = None) -> None:
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

# ── Charts (Altair, pastel) ─────────────────────────────────────────────────
def area_chart(df: pd.DataFrame, x: str, y: str, title: Optional[str] = None):
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

def bar_chart(df: pd.DataFrame, x: str, y: str, title: Optional[str] = None):
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

# ── Money formatting ─────────────────────────────────────────────────────────
def fmt_money(value: Optional[Number], currency: str, decimals: int = 2) -> str:
    """
    Format numeric values with thousand separators and append currency code.
    Examples:
      fmt_money(12345.6, "KRW") -> "12,345.60 KRW"
      fmt_money(None, "USD")    -> "—"
    """
    if value is None:
        return "—"
    try:
        v = float(value)
    except Exception:
        return f"{value} {currency}"
    fmt = f"{{:,.{decimals}f}}"
    return f"{fmt.format(v)} {currency}"
