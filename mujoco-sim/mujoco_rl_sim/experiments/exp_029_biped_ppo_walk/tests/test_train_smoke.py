"""train.py の 1-update スモーク（学習パイプライン全体）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_EXP_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.slow
def test_train_one_update_smoke() -> None:
  """seed 固定・wandb 無効で 1 update が落ちず、config_effective.json を書く。"""
  env = os.environ.copy()
  env["WANDB_MODE"] = "disabled"

  result = subprocess.run(
    [
      sys.executable,
      "train.py",
      "--seed",
      "0",
      "--num-updates",
      "1",
      "--no-viewer",
      "--no-telemetry",
      "--no-wandb",
      "--no-eval",
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

  runs_root = _EXP_ROOT.parent.parent / "runs" / "exp_029_biped_ppo_walk"
  run_dirs = sorted(
    (p for p in runs_root.iterdir() if p.is_dir()),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
  )
  assert run_dirs, f"checkpoint run dir not found under {runs_root}"
  cfg_path = run_dirs[0] / "config_effective.json"
  assert cfg_path.is_file(), f"missing {cfg_path}"
  snapshot = json.loads(cfg_path.read_text(encoding="utf-8"))
  assert snapshot.get("training_seed") == 0
