# tests/test_transactions_edit.py
from ledger.db import bootstrap, add_account, add_transaction, list_transactions_joined, update_transaction, soft_delete_transaction

def test_update_and_soft_delete(tmp_path):
    dbp = tmp_path / "db.sqlite3"
    conn = bootstrap(str(dbp))
    aid = add_account(conn, "TestAcc", "Chase", "USD", "card", 0.0)
    tid = add_transaction(
        conn,
        date_utc="2025-10-01T00:00:00Z",
        amount=10.0,
        currency="USD",
        category="Food",
        account_id=aid,
        direction="debit",
        payee="Cafe",
    )

    # update
    rc = update_transaction(conn, tid, category="Coffee", notes="edit test")
    assert rc == 1
    row = list_transactions_joined(conn, limit=1)[0]
    assert row["category"] == "Coffee"
    assert row["notes"] == "edit test"

    # soft delete
    rc = soft_delete_transaction(conn, tid, True)
    assert rc == 1
    rows = list_transactions_joined(conn, include_deleted=False, limit=10)
    assert len(rows) == 0  # 숨김
