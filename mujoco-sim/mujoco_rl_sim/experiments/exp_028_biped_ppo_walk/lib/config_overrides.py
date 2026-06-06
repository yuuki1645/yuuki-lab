"""config.py 定数の run 単位上書き（CLI ``--set`` / dispatch 環境変数）。

snake_case キー → ``config`` モジュールの属性名。新しい上書き可能項目は
``OVERRIDABLE_CONFIG_KEYS`` に追加する。
"""

from __future__ import annotations

import json
import os
from typing import Any

import config

# sweep YAML / CLI --set / DISPATCH_CONFIG_OVERRIDES_JSON 共通の snake_case キー表
OVERRIDABLE_CONFIG_KEYS: dict[str, str] = {
  # 報酬 ENABLE 群（bool）
  "reward_enable_forward": "REWARD_ENABLE_FORWARD",
  "reward_enable_forward_foot": "REWARD_ENABLE_FORWARD_FOOT",
  "reward_enable_progress": "REWARD_ENABLE_PROGRESS",
  "reward_enable_walk_shaping": "REWARD_ENABLE_WALK_SHAPING",
  "reward_enable_upright_bonus": "REWARD_ENABLE_UPRIGHT_BONUS",
  "reward_enable_posture_penalties": "REWARD_ENABLE_POSTURE_PENALTIES",
  "reward_enable_double_support": "REWARD_ENABLE_DOUBLE_SUPPORT",
  "reward_enable_flight_duration": "REWARD_ENABLE_FLIGHT_DURATION",
  "reward_enable_effort": "REWARD_ENABLE_EFFORT",
  # 報酬係数
  "double_support_penalty_scale": "DOUBLE_SUPPORT_PENALTY_SCALE",
  "alternating_landing_bonus_scale": "ALTERNATING_LANDING_BONUS_SCALE",
  "forward_reward_scale": "FORWARD_REWARD_SCALE",
  "swing_clearance_bonus_scale": "SWING_CLEARANCE_BONUS_SCALE",
  "landing_bonus_scale": "LANDING_BONUS_SCALE",
  "push_off_bonus_scale": "PUSH_OFF_BONUS_SCALE",
  "aerial_duration_penalty_after_steps": "AERIAL_DURATION_PENALTY_AFTER_STEPS",
  "forward_require_single_support": "FORWARD_REQUIRE_SINGLE_SUPPORT",
  "forward_imu_lean_gate": "FORWARD_IMU_LEAN_GATE",
  # 終了 — 姿勢（sim/termination.py）
  "min_imu_z": "MIN_IMU_Z",
  "min_imu_z_stance": "MIN_IMU_Z_STANCE",
  "min_imu_upright": "MIN_IMU_UPRIGHT",
  "max_backward_lean_body": "MAX_BACKWARD_LEAN_BODY",
  "pose_termination_penalty": "POSE_TERMINATION_PENALTY",
  "contact_shank_terminates": "CONTACT_SHANK_TERMINATES",
}

# 後方互換（README / sweep 文書の旧名称）
SWEEPABLE_CONFIG_KEYS = OVERRIDABLE_CONFIG_KEYS


def _coerce_override_value(attr: str, raw: Any) -> Any:
  """CLI 文字列などを config 属性の型に合わせて変換する。"""
  if not isinstance(raw, str):
    return raw

  text = raw.strip()
  current = getattr(config, attr)

  if isinstance(current, bool):
    lower = text.lower()
    if lower in ("true", "yes", "1", "on"):
      return True
    if lower in ("false", "no", "0", "off"):
      return False
    raise ValueError(
      f"bool 型の {attr} には true/false を指定してください（got {raw!r}）"
    )

  if isinstance(current, int):
    try:
      return int(text, 0)
    except ValueError as exc:
      raise ValueError(f"int 型の {attr} に整数を指定してください: {raw!r}") from exc

  if isinstance(current, float):
    try:
      return float(text)
    except ValueError as exc:
      raise ValueError(f"float 型の {attr} に数値を指定してください: {raw!r}") from exc

  if isinstance(current, tuple):
    raise ValueError(f"tuple 型の {attr} は --set では上書きできません")

  return text


def parse_set_argument(raw: str) -> tuple[str, Any]:
  """``key=value`` 形式の CLI 引数を (snake_case key, 型変換済み value) に分解する。"""
  text = str(raw).strip()
  if "=" not in text:
    raise ValueError(f"--set は key=value 形式です: {raw!r}")

  key, _, value_part = text.partition("=")
  key = key.strip()
  if not key:
    raise ValueError(f"--set のキーが空です: {raw!r}")

  attr = OVERRIDABLE_CONFIG_KEYS.get(key)
  if attr is None:
    known = ", ".join(sorted(OVERRIDABLE_CONFIG_KEYS))
    raise ValueError(f"未対応の --set キー: {key!r}（利用可能: {known}）")

  return key, _coerce_override_value(attr, value_part.strip())


def apply_config_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
  """辞書の内容を config モジュールに反映し、適用した {key: value} を返す。"""
  applied: dict[str, Any] = {}
  for key, value in overrides.items():
    attr = OVERRIDABLE_CONFIG_KEYS.get(str(key))
    if attr is None:
      raise ValueError(f"未対応の config 上書きキー: {key}")
    coerced = _coerce_override_value(attr, value)
    setattr(config, attr, coerced)
    applied[str(key)] = coerced
  return applied


def apply_dispatch_env_overrides() -> dict[str, Any]:
  """環境変数 DISPATCH_CONFIG_OVERRIDES_JSON を読み config に反映する。"""
  raw = os.environ.get("DISPATCH_CONFIG_OVERRIDES_JSON", "").strip()
  if not raw:
    return {}

  payload = json.loads(raw)
  if not isinstance(payload, dict):
    raise ValueError("DISPATCH_CONFIG_OVERRIDES_JSON は JSON object である必要があります")
  return apply_config_overrides(payload)


def apply_cli_set_overrides(set_args: list[str] | tuple[str, ...]) -> dict[str, Any]:
  """``--set key=value`` のリストを config に反映する。"""
  if not set_args:
    return {}

  overrides: dict[str, Any] = {}
  for raw in set_args:
    key, value = parse_set_argument(raw)
    overrides[key] = value
  return apply_config_overrides(overrides)


# 後方互換（train.py / dispatch 文書）
apply_dispatch_config_overrides = apply_dispatch_env_overrides
