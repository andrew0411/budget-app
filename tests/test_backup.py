# tests/test_backup.py
from ledger.backup import create_backup, list_backups, prune_backups
from ledger.db import bootstrap

def test_backup_cycle(tmp_path):
    dbp = tmp_path / "db.sqlite3"
    conn = bootstrap(str(dbp))

    # 백업 3개 생성
    b1 = create_backup(dbp, tmp_path, prefix="t", keep_last=None)
    b2 = create_backup(dbp, tmp_path, prefix="t", keep_last=None)
    b3 = create_backup(dbp, tmp_path, prefix="t", keep_last=None)

    backs = list_backups(tmp_path, prefix="t", limit=10)
    assert len(backs) >= 3

    # 2개만 보존
    pruned = prune_backups(tmp_path, prefix="t", keep_last=2)
    assert pruned >= 1
    backs2 = list_backups(tmp_path, prefix="t", limit=10)
    assert len(backs2) == 2
