"""mujoco_rl_sim ルートと実験ディレクトリの解決。"""

from __future__ import annotations

import os
from pathlib import Path

_DISPATCH_PKG = Path(__file__).resolve().parent
MUJOCO_RL_SIM_ROOT = _DISPATCH_PKG.parent
EXPERIMENTS_ROOT = MUJOCO_RL_SIM_ROOT / "experiments"
RUNS_ROOT = MUJOCO_RL_SIM_ROOT / "runs"

_DEFAULT_DATA = MUJOCO_RL_SIM_ROOT / "dispatch_data"


def dispatch_data_dir() -> Path:
  raw = os.environ.get("MUJOCO_DISPATCH_DATA_DIR", "").strip()
  if raw:
    return Path(raw).expanduser().resolve()
  return _DEFAULT_DATA


def default_db_path() -> Path:
  return dispatch_data_dir() / "coordinator.db"


def resolve_experiment_dir(exp_id: str, *, archive: bool = False) -> Path:
  """実験ディレクトリを返す。archive 実験は ``experiments/archive/<exp_id>``。"""
  if archive:
    path = EXPERIMENTS_ROOT / "archive" / exp_id
  else:
    path = EXPERIMENTS_ROOT / exp_id
  if not path.is_dir():
    label = "archive/" if archive else ""
    raise FileNotFoundError(f"実験ディレクトリがありません: {label}{exp_id}")
  return path


def experiment_dir(exp_id: str) -> Path:
  return resolve_experiment_dir(exp_id, archive=False)
