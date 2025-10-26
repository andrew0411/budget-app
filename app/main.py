import streamlit as st
st.set_page_config(page_title="Budget App", page_icon="💸", layout="wide")

st.title("💸 Budget App (Pastel Ledger)")
st.caption("Local-first, beginner-friendly personal finance tracker")

with st.container():
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Assets (base)", "—", help="Will show KRW or USD once data is loaded")
    c2.metric("Month-to-date Spend", "—")
    c3.metric("FX (USD→KRW)", "—", help="FRED DEXKOUS as-of date will appear here")

st.success("Scaffold OK. Next: DB schema, CSV import, FX provider.")
