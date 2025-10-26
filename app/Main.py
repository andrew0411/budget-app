from pathlib import Path
from datetime import datetime, timezone, timedelta

import streamlit as st
import os
from app.ui import inject_css, metric_card, fmt_money

from ledger.db import (
    bootstrap,
    count_rows,
    ensure_default_accounts,
    get_latest_fx,
    upsert_fx_cache_many,
)
from ledger.fx.fred import fetch_dexkous, SOURCE_LABEL
from ledger.backup import ensure_daily_backup, create_backup, list_backups

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Budget App — Main", page_icon="💸", layout="wide")

st.title("💸 Budget App — Main")
inject_css()
st.caption("Local-first, beginner-friendly personal finance tracker")

# ── DB bootstrap ──────────────────────────────────────────────────────────────
DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")

with st.sidebar:
    st.subheader("Database")
    try:
        conn = bootstrap(DB_PATH)
        # 보장: KRW/USD 기본 계정 존재
        ensure_default_accounts(conn, currencies=("KRW", "USD"))
        acc_n = count_rows(conn, "accounts")
        txn_n = count_rows(conn, "transactions")
        st.success(f"Connected · accounts={acc_n}, transactions={txn_n}")
    except Exception as e:
        st.error(f"DB error: {e}")

    st.divider()

    # ── FX (USD→KRW) ─────────────────────────────────────────────────────────
    with st.expander("FX · USD→KRW", expanded=True):
        latest = get_latest_fx(conn, "USD", "KRW")
        col_fx, col_btn = st.columns([2, 1])
        with col_fx:
            if latest:
                metric_card(
                    "USD→KRW",
                    fmt_money(latest["rate"], "KRW"),
                    sub=f"As of {latest['date_utc']} • {latest['source']}",
                )
            else:
                st.warning("No FX cached yet.")

        with col_btn:
            if st.button("Fetch latest", help="Fetch last ~14 days from FRED (DEXKOUS)"):
                try:
                    end = datetime.now(timezone.utc).date()
                    start = end - timedelta(days=14)
                    observations = fetch_dexkous(start, end)  # 외부 API 호출
                    rows = [(o["date"], "USD", "KRW", o["rate"], SOURCE_LABEL) for o in observations]
                    n = upsert_fx_cache_many(conn, rows)
                    st.toast(f"FX updated: {n} row(s)", icon="✅")
                except Exception as e:
                    st.error(f"Fetch failed: {e}")
                # 새로고침용 재표시
                latest = get_latest_fx(conn, "USD", "KRW")
                if latest:
                    metric_card(
                        "USD→KRW",
                        fmt_money(latest["rate"], "KRW"),
                        sub=f"As of {latest['date_utc']} • {latest['source']}",
                    )

    st.divider()

    # ── Backups (auto daily + manual) ─────────────────────────────────────────
    with st.expander("Backups", expanded=False):
        try:
            # 하루 1회 자동, 최근 5개만 보관
            created_today = ensure_daily_backup(DB_PATH, keep_last=5)
            if created_today:
                st.success("Created today's auto backup.")
        except Exception as e:
            st.warning(f"Auto-backup skipped: {e}")

        if st.button("Create backup now"):
            try:
                dest = create_backup(DB_PATH, keep_last=5)
                st.success(f"Backup: {dest.name}")
            except Exception as e:
                st.error(f"Backup failed: {e}")

        st.caption("Recent backups (max 5)")
        backs = list_backups(limit=5)
        if backs:
            for b in backs:
                st.write("• ", b.name)
        else:
            st.write("No backups yet")

    st.divider()
    if st.button("Quit app", type="secondary", help="Terminate the local server"):
        os._exit(0)

# ── Top metrics (placeholder; real values show on other pages) ───────────────
c1, c2, c3 = st.columns(3)
c1.metric("Total Assets (base)", "—", help="Will appear after data & FX")
c2.metric("Month-to-date Spend", "—")

fx_latest = get_latest_fx(conn, "USD", "KRW") if "conn" in locals() else None
c3.metric(
    "FX (USD→KRW)",
    fmt_money(fx_latest["rate"], "KRW") if fx_latest else "—",
    help="Open FX section in sidebar for details",
)

st.info("Welcome! Use **Import**, **Quick Add**, and **Budget** to get started.")
