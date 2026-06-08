"""train.py の 1-update スモーク（学習パイプライン全体）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from lib.hydra_checkpoint import hydra_config_path

_EXP_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.slow
def test_train_one_update_smoke() -> None:
  """seed 固定・wandb 無効で 1 update が落ちず、.hydra/config.yaml を書く。"""
  env = os.environ.copy()
  env["WANDB_MODE"] = "disabled"

  result = subprocess.run(
    [
      sys.executable,
      "train.py",
      "training.seed=0",
      "training.num_updates=1",
      "wandb=disabled",
      "training.post_train_eval=false",
    ],
    cwd=_EXP_ROOT,
    env=env,
    capture_output=True,
    text=True,
    timeout=300,
    check=False,
  )
  assert result.returncode == 0, (
    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
  )
  assert "training seed=0" in result.stdout

  runs_root = _EXP_ROOT.parent.parent / "runs" / "exp_030_biped_ppo_walk"
  run_dirs = sorted(
    (p for p in runs_root.iterdir() if p.is_dir()),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
  )
  assert run_dirs, f"checkpoint run dir not found under {runs_root}"
  cfg_path = hydra_config_path(run_dirs[0])
  assert cfg_path.is_file(), f"missing {cfg_path}"


@pytest.mark.slow
def test_train_one_update_subproc_smoke() -> None:
  """Subproc VecEnv (num_envs=2) で 1 update が完走する。"""
  env = os.environ.copy()
  env["WANDB_MODE"] = "disabled"

  result = subprocess.run(
    [
      sys.executable,
      "train.py",
      "training.seed=0",
      "training.num_updates=1",
      "runtime.num_envs=2",
      "wandb=disabled",
      "training.post_train_eval=false",
    ],
    cwd=_EXP_ROOT,
    env=env,
    capture_output=True,
    text=True,
    timeout=300,
    check=False,
  )
  assert result.returncode == 0, (
    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
  )
  assert "[subproc-vec] enabled: 2 env workers" in result.stdout
