"""MuJoCo 強化学習用の環境・タスク（実時間 HTTP サーバとは別プロセス想定）。"""

from __future__ import annotations

# `mujoco_rl_sim` を `python -m ...` で直接起動したときに、
# 配下の共通パッケージ（`mujoco_sim_common` 等）が解決できない環境があるため、
# このファイルの親ディレクトリ（`mujoco-sim/`）を sys.path に入れて解決を安定化する。
import sys
from pathlib import Path

_PKG_ROOT = str(Path(__file__).resolve().parent.parent)
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from mujoco_rl_sim.envs import Env002FullActuators, Env003StaticActuators, KneeTrackEnv

__all__ = ["Env002FullActuators", "Env003StaticActuators", "KneeTrackEnv"]
