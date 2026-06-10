"""exp_030 環境へのブリッジ（MuJoCo モデル・物理は RL 実験と同一）。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

from runtime.config import RunConfig


def install_exp030(exp030_dir: Path) -> None:
  """exp_030 を sys.path 先頭に載せ、lib/sim 等を import 可能にする。"""
  root = str(exp030_dir.resolve())
  if root in sys.path:
    sys.path.remove(root)
  sys.path.insert(0, root)


def create_env(
  run_cfg: RunConfig,
  *,
  enable_viewer: bool = False,
) -> Any:
  """EnvBipedPPO を構築（DR 無効・決定的 stand）。"""
  install_exp030(run_cfg.exp030_dir)
  from conf.schema import build_app_config
  from lib.experiment_context import build_experiment_context
  from sim.env import EnvBipedPPO

  ctx = build_experiment_context(build_app_config())
  return EnvBipedPPO(
    ctx,
    enable_viewer=enable_viewer,
    training_dr_enabled=False,
    training_seed=run_cfg.seed,
  )


def reset_env(env: Any, *, seed: int) -> tuple[np.ndarray, float]:
  """決定的 reset（episode_index=0）。"""
  _ = seed
  obs = env.reset(episode_index=0)
  imu_x = float(env.data.site("imu_site").xpos[0])
  return np.asarray(obs, dtype=np.float64), imu_x
