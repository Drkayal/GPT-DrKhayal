#!/usr/bin/env python3
import os
import tarfile
import time
from pathlib import Path


def main() -> int:
    home = Path.home()
    src = home / ".openhands"
    if not src.exists():
        print("[backup] ~/.openhands not found; skipping")
        return 0

    backup_dir = home / ".openhands_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    dst = backup_dir / f"openhands-{ts}.tar.gz"

    try:
        with tarfile.open(dst, "w:gz") as tar:
            tar.add(src, arcname=".openhands")
        print(f"[backup] created: {dst}")
        return 0
    except Exception as e:
        print(f"[backup] failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())