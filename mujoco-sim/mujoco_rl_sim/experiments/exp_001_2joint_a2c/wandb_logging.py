"""exp_001 用の任意 Weights & Biases ロギング。"""

from __future__ import annotations

import os
from typing import Any

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config

_active = False


def is_enabled() -> bool:
  if not config.USE_WANDB:
    return False
  if os.environ.get("WANDB_MODE", "").lower() == "disabled":
    return False
  return True


def init() -> bool:
  """wandb.run を開始する。無効・未インストール時は False。"""
  global _active
  if not is_enabled():
    return False

  try:
    import wandb
  except ImportError:
    print("[wandb] 未インストールです: pip install wandb  または USE_WANDB=False")
    return False

  init_kwargs: dict[str, Any] = {
    "project": config.WANDB_PROJECT,
    "config": config.training_config_dict(),
    "tags": list(config.WANDB_TAGS),
  }
  if config.WANDB_RUN_NAME:
    init_kwargs["name"] = config.WANDB_RUN_NAME
  if config.WANDB_ENTITY:
    init_kwargs["entity"] = config.WANDB_ENTITY

  wandb.init(**init_kwargs)
  _active = True
  return True


def log(metrics: dict[str, float], *, step: int) -> None:
  if not _active:
    return
  import wandb

  wandb.log(metrics, step=step)


def finish() -> None:
  global _active
  if not _active:
    return
  import wandb

  wandb.finish()
  _active = False
