"""チェックポイント run ディレクトリ名（wandb Run Name 連携）。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_run_dir_name(name: str) -> str:
  """ファイルシステム向けに wandb Run Name を安全化する。"""
  s = str(name).strip()
  s = _INVALID_CHARS.sub("_", s)
  s = s.strip(". ")
  return s or "wandb_run"


def timestamp_run_dir_label() -> str:
  return datetime.now().strftime("run_%Y%m%d_%H%M%S")


def resolve_run_dir_label(*, wandb_run_name: str | None) -> str:
  """run ディレクトリ名（wandb Name 優先、無ければ時刻）。"""
  if wandb_run_name and str(wandb_run_name).strip():
    return sanitize_run_dir_name(wandb_run_name)
  return timestamp_run_dir_label()


def make_unique_run_dir(base: Path, label: str) -> Path:
  """base/label を作成。既存なら label_2, label_3 …"""
  candidate = base / label
  if not candidate.exists():
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate
  for i in range(2, 1000):
    candidate = base / f"{label}_{i}"
    if not candidate.exists():
      candidate.mkdir(parents=True, exist_ok=True)
      return candidate
  raise RuntimeError(f"could not allocate unique run dir under {base} for {label!r}")


def wandb_active_run_name() -> str | None:
  """初期化済み wandb run の Name（未設定時は id）。"""
  try:
    import wandb
  except ImportError:
    return None
  if wandb.run is None:
    return None
  name = getattr(wandb.run, "name", None) or getattr(wandb.run, "id", None)
  if name is None:
    return None
  text = str(name).strip()
  return text or None
