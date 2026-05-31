"""スタンドアロン実行: 実験フォルダを sys.path 先頭に載せる。"""

from __future__ import annotations

import sys
from pathlib import Path

_EXP_ROOT = Path(__file__).resolve().parent


def install() -> Path:
  root = str(_EXP_ROOT)
  if root not in sys.path:
    sys.path.insert(0, root)
  return _EXP_ROOT
