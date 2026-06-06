"""exp_029 pytest: 実験ルートを import パスに追加し、config 変異を隔離する。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
  sys.path.insert(0, str(_ROOT))


@pytest.fixture
def restore_config() -> Any:
  """``apply_config_overrides`` 等で変えた config 定数をテスト後に元に戻す。"""
  import config
  from lib.config_overrides import OVERRIDABLE_CONFIG_KEYS

  snapshot: dict[str, Any] = {
    attr: getattr(config, attr) for attr in OVERRIDABLE_CONFIG_KEYS.values()
  }
  yield
  for attr, value in snapshot.items():
    setattr(config, attr, value)
