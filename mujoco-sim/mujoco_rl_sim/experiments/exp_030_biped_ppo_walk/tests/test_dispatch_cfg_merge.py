"""dispatch 由来の Hydra cfg マージの単体テスト。"""

from __future__ import annotations

import json

import pytest
from omegaconf import OmegaConf

from lib.dispatch_cfg_merge import DISPATCH_KEY_TO_CFG_PATH, merge_dispatch_overrides
from lib.hydra_compose import compose_cfg


def test_dispatch_key_mapping_contains_reward_scale() -> None:
  assert DISPATCH_KEY_TO_CFG_PATH["forward_reward_scale"] == "reward.forward_reward_scale"


def test_merge_dispatch_overrides(monkeypatch) -> None:
  monkeypatch.setenv(
    "DISPATCH_CONFIG_OVERRIDES_JSON",
    json.dumps({"forward_reward_scale": 77.0, "seed": 3}),
  )
  cfg = compose_cfg()
  merged = merge_dispatch_overrides(cfg)
  assert float(merged.reward.forward_reward_scale) == 77.0
  assert int(merged.training.seed) == 3


def test_merge_dispatch_rejects_unknown_key(monkeypatch) -> None:
  monkeypatch.setenv(
    "DISPATCH_CONFIG_OVERRIDES_JSON",
    json.dumps({"not_a_real_key": 1}),
  )
  cfg = compose_cfg()
  with pytest.raises(ValueError, match="未対応"):
    merge_dispatch_overrides(cfg)
