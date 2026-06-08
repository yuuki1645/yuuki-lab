"""exp_029 pytest: 実験ルートを import パスに追加し、Hydra fixture を提供する。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
  sys.path.insert(0, str(_ROOT))


@pytest.fixture
def default_ctx():
  """``conf/config.yaml`` 既定の ``ExperimentContext``。"""
  from lib.load_run_context import default_ctx as _default_ctx

  return _default_ctx()


@pytest.fixture
def smoke_ctx():
  """スモーク学習向けの短い設定。"""
  from lib.experiment_context import build_experiment_context
  from lib.hydra_compose import compose_app_config

  return build_experiment_context(
    compose_app_config(["training=smoke", "wandb=disabled", "runtime=fast"])
  )
