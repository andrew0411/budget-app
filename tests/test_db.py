# tests/test_db.py
from ledger.db import bootstrap, add_account, add_transaction, count_rows

def test_db_roundtrip(tmp_path):
    dbp = tmp_path / "test.sqlite3"
    conn = bootstrap(str(dbp))
    aid = add_account(conn, name="Test", institution=None, currency="KRW")
    add_transaction(
        conn,
        date_utc="2025-01-01T00:00:00Z",
        amount=1234.5,
        currency="KRW",
        category="Food",
        account_id=aid,
        direction="debit",
    )
    assert count_rows(conn, "accounts") == 1
    assert count_rows(conn, "transactions") == 1
