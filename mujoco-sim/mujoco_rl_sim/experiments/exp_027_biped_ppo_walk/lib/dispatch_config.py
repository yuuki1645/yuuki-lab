"""dispatch sweep から config.py 定数を上書きする。"""

from __future__ import annotations

import json
import os
from typing import Any

import config

# sweep YAML の snake_case → config 属性名
SWEEPABLE_CONFIG_KEYS: dict[str, str] = {
  "double_support_penalty_scale": "DOUBLE_SUPPORT_PENALTY_SCALE",
  "alternating_landing_bonus_scale": "ALTERNATING_LANDING_BONUS_SCALE",
  "forward_reward_scale": "FORWARD_REWARD_SCALE",
  "swing_clearance_bonus_scale": "SWING_CLEARANCE_BONUS_SCALE",
  "landing_bonus_scale": "LANDING_BONUS_SCALE",
  "push_off_bonus_scale": "PUSH_OFF_BONUS_SCALE",
  "aerial_duration_penalty_after_steps": "AERIAL_DURATION_PENALTY_AFTER_STEPS",
}


def apply_dispatch_config_overrides() -> dict[str, Any]:
  """環境変数 DISPATCH_CONFIG_OVERRIDES_JSON を読み config に反映する。"""
  raw = os.environ.get("DISPATCH_CONFIG_OVERRIDES_JSON", "").strip()
  if not raw:
    return {}

  payload = json.loads(raw)
  if not isinstance(payload, dict):
    raise ValueError("DISPATCH_CONFIG_OVERRIDES_JSON は JSON object である必要があります")

  applied: dict[str, Any] = {}
  for key, value in payload.items():
    attr = SWEEPABLE_CONFIG_KEYS.get(str(key))
    if attr is None:
      raise ValueError(f"未対応の sweep キー: {key}")
    setattr(config, attr, value)
    applied[str(key)] = value
  return applied
