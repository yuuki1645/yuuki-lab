"""ディスク空き容量チェック。"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiskStatus:
  path: str
  free_bytes: int
  total_bytes: int
  ok_for_record: bool
  warning: str | None = None


def disk_status(path: Path, min_free_bytes: int) -> DiskStatus:
  """path が属するボリュームの空きを調べる。"""
  path.mkdir(parents=True, exist_ok=True)
  usage = shutil.disk_usage(path)
  ok = usage.free >= min_free_bytes
  warning = None
  if not ok:
    free_gb = usage.free / (1024**3)
    need_gb = min_free_bytes / (1024**3)
    warning = f"空き容量不足: {free_gb:.1f} GiB（必要目安 {need_gb:.1f} GiB）"
  return DiskStatus(
    path=str(path),
    free_bytes=usage.free,
    total_bytes=usage.total,
    ok_for_record=ok,
    warning=warning,
  )
