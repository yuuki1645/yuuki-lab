"""Where closed takes live.

LAB_EXPERIMENTS_ROOT wins. Otherwise the archive_root line in the user's
storage.yaml. This file does not name a machine or a share.
"""

from __future__ import annotations

import os
from pathlib import Path


def _archive_from_storage() -> Path | None:
    """archive_root from ~/.yuuki-lab/storage.yaml. Missing file means unset."""
    file = Path.home() / ".yuuki-lab" / "storage.yaml"
    if not file.is_file():
        return None
    try:
        text = file.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line.startswith("archive_root"):
            continue
        _, _, value = line.partition(":")
        path = value.strip().strip('"').strip("'")
        if path:
            # Do not resolve. A disconnected share must not raise here.
            return Path(path).expanduser()
    return None


def lab_experiments_root() -> Path:
    """Folder of year/month/day/take. May not exist yet."""
    raw = (os.getenv("LAB_EXPERIMENTS_ROOT") or "").strip()
    if raw:
        return Path(raw).expanduser()
    archive = _archive_from_storage()
    if archive is not None:
        return archive
    # Not a real folder. The day list then reports available=false.
    return Path.home() / ".yuuki-lab" / "archive-unset"
