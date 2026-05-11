"""MuJoCo 実時間シミュ（HTTP API + 共有 ``MjData`` + オプション Viewer）。"""

from __future__ import annotations

# `mujoco_realtime_sim` を `python -m ...` で直接起動したときに、
# 同梱の共通パッケージ（`mujoco_sim_common` 等）が解決できない環境があるため、
# このファイルの親ディレクトリ（`mujoco-sim/`）を sys.path に入れて解決を安定化する。
import sys
from pathlib import Path

_PKG_ROOT = str(Path(__file__).resolve().parent.parent)
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

__version__ = "0.1.0"
