"""MuJoCo 強化学習用パッケージ（実時間 HTTP サーバとは別プロセス想定）。

環境・エージェントは ``mujoco_rl_sim.experiments.<実験名>`` に配置する。
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKG_ROOT = str(Path(__file__).resolve().parent.parent)
if _PKG_ROOT not in sys.path:
  sys.path.insert(0, _PKG_ROOT)

__all__: list[str] = []
