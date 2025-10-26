from __future__ import annotations
from pathlib import Path
from datetime import datetime
import shutil

def _backups_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def create_backup(db_path: str | Path, backups_dir: str | Path = "backups",
                  prefix: str = "ledger", keep_last: int | None = 30) -> Path:
    backups = _backups_dir(backups_dir)
    # 🔧 초·마이크로초까지 포함해 충돌 최소화
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = backups / f"{prefix}_{ts}.sqlite"

    # 🔧 혹시라도 동일 타임스탬프 충돌 시 증분 접미사로 보장
    i = 1
    while dest.exists():
        dest = backups / f"{prefix}_{ts}_{i}.sqlite"
        i += 1

    shutil.copy2(str(db_path), str(dest))

    if keep_last is not None:
        prune_backups(backups, prefix, keep_last)

    return dest

def list_backups(backups_dir: str | Path = "backups", prefix: str = "ledger", limit: int = 10):
    backups = _backups_dir(backups_dir)
    files = sorted(backups.glob(f"{prefix}_*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]

def prune_backups(backups_dir: str | Path, prefix: str = "ledger", keep_last: int = 30) -> int:
    backups = _backups_dir(backups_dir)
    files = sorted(backups.glob(f"{prefix}_*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
    deleted = 0
    for f in files[keep_last:]:
        try:
            f.unlink()
            deleted += 1
        except Exception:
            pass
    return deleted

def ensure_daily_backup(db_path: str | Path, backups_dir: str | Path = "backups", prefix: str = "ledger") -> bool:
    backups = _backups_dir(backups_dir)
    today = datetime.now().strftime("%Y%m%d")
    # ✅ seconds/microseconds 포함 파일명도 이 패턴에 걸림
    existing = list(backups.glob(f"{prefix}_{today}_*.sqlite"))
    if existing:
        return False
    create_backup(db_path, backups_dir, prefix)
    return True
