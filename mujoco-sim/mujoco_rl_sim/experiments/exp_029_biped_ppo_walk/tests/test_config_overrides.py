"""config --set / dispatch 上書きの単体テスト。"""

from __future__ import annotations

import json

import pytest

import config
from lib.config_overrides import (
  apply_cli_set_overrides,
  apply_dispatch_env_overrides,
  parse_set_argument,
)


def test_parse_set_float_key() -> None:
  key, value = parse_set_argument("forward_reward_scale=55.0")
  assert key == "forward_reward_scale"
  assert value == 55.0


def test_parse_set_bool_key() -> None:
  key, value = parse_set_argument("reward_enable_walk_shaping=true")
  assert key == "reward_enable_walk_shaping"
  assert value is True


def test_parse_set_rejects_unknown_key() -> None:
  with pytest.raises(ValueError, match="未対応"):
    parse_set_argument("not_a_real_key=1")


def test_apply_cli_set_overrides(restore_config) -> None:
  before = config.FORWARD_REWARD_SCALE
  applied = apply_cli_set_overrides(["forward_reward_scale=77.0"])
  assert applied["forward_reward_scale"] == 77.0
  assert config.FORWARD_REWARD_SCALE == 77.0
  # restore_config が after で元に戻す
  assert before != 77.0 or before == 77.0


def test_apply_dispatch_env_overrides(monkeypatch, restore_config) -> None:
  monkeypatch.setenv(
    "DISPATCH_CONFIG_OVERRIDES_JSON",
    json.dumps({"double_support_penalty_scale": 9.5}),
  )
  applied = apply_dispatch_env_overrides()
  assert applied["double_support_penalty_scale"] == 9.5
  assert config.DOUBLE_SUPPORT_PENALTY_SCALE == 9.5
