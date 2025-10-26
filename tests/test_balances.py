# tests/test_balances.py
from ledger.db import bootstrap, add_account, add_transaction
from ledger.db import balances_in_base
import sqlite3

def test_balances_and_total(tmp_path):
    dbp = tmp_path / "test.sqlite3"
    conn = bootstrap(str(dbp))

    # KRW 계정: opening=100000, 지출 20000, 수입 5000 -> 85,000 KRW
    aid1 = add_account(conn, "KRW Wallet", None, "KRW", "cash", 100000)
    add_transaction(conn, date_utc="2025-10-01T00:00:00Z", amount=20000, currency="KRW",
                    category="Food", account_id=aid1, direction="debit")
    add_transaction(conn, date_utc="2025-10-02T00:00:00Z", amount=5000, currency="KRW",
                    category="Gift", account_id=aid1, direction="credit")

    # USD 계정: opening=100 USD -> 환율 1300 가정 시 130,000 KRW
    conn.execute("INSERT INTO fx_cache(date_utc, base, quote, rate, source) VALUES(?,?,?,?,?)",
                 ("2025-10-01", "USD", "KRW", 1300.0, "test"))
    aid2 = add_account(conn, "USD Cash", None, "USD", "cash", 100)

    out = balances_in_base(conn, base="KRW")
    total = out["total_base"]
    # 85,000 + 130,000 = 215,000
    assert round(total, 2) == 215000.0
