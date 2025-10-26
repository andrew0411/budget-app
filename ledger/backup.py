from __future__ import annotations
from pathlib import Path
from datetime import datetime
import shutil

def _backups_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def create_backup(
    db_path: str | Path,
    backups_dir: str | Path = "backups",
    prefix: str = "ledger",
    keep_last: int | None = 10,
) -> Path:
    """
    Copy db file into backups_dir with timestamped name.
    If keep_last is not None, prune old backups keeping the most recent N.
    """
    backups = _backups_dir(backups_dir)
    # include seconds + microseconds to avoid collisions
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = backups / f"{prefix}_{ts}.sqlite"

    # last resort: ensure uniqueness if same ts somehow appears
    i = 1
    while dest.exists():
        dest = backups / f"{prefix}_{ts}_{i}.sqlite"
        i += 1

    shutil.copy2(str(db_path), str(dest))

    if keep_last is not None:
        prune_backups(backups, prefix, keep_last)

    return dest

def list_backups(
    backups_dir: str | Path = "backups",
    prefix: str = "ledger",
    limit: int = 10,
):
    backups = _backups_dir(backups_dir)
    files = sorted(
        backups.glob(f"{prefix}_*.sqlite"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:limit]

def prune_backups(
    backups_dir: str | Path,
    prefix: str = "ledger",
    keep_last: int = 10,
) -> int:
    backups = _backups_dir(backups_dir)
    files = sorted(
        backups.glob(f"{prefix}_*.sqlite"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    deleted = 0
    for f in files[keep_last:]:
        try:
            f.unlink()
            deleted += 1
        except Exception:
            pass
    return deleted

def ensure_daily_backup(
    db_path: str | Path,
    backups_dir: str | Path = "backups",
    prefix: str = "ledger",
    keep_last: int | None = 10,
) -> bool:
    """
    Ensure only one backup per day exists.
    Returns True if a new backup was created, False if today's backup already exists.
    Also prunes to keep the most recent `keep_last` backups when creating a new one.
    """
    backups = _backups_dir(backups_dir)
    today = datetime.now().strftime("%Y%m%d")
    # seconds/microseconds are part of filenames; this glob matches today's files
    existing = list(backups.glob(f"{prefix}_{today}_*.sqlite"))
    if existing:
        return False
    # create new daily backup and prune according to keep_last
    create_backup(
        db_path=db_path,
        backups_dir=backups_dir,
        prefix=prefix,
        keep_last=keep_last,
    )
    return True
