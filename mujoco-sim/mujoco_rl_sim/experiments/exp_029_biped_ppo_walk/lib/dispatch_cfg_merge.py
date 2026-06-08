"""dispatch 由来の上書きを Hydra cfg へマージする。"""

from __future__ import annotations

import json
import os
from typing import Any

from omegaconf import DictConfig, OmegaConf

# 旧 --set / dispatch キーを Hydra のネストパスへ写像する。
DISPATCH_KEY_TO_CFG_PATH: dict[str, str] = {
  # 報酬 ENABLE
  "reward_enable_forward": "reward.enable_forward",
  "reward_enable_forward_foot": "reward.enable_forward_foot",
  "reward_enable_progress": "reward.enable_progress",
  "reward_enable_walk_shaping": "reward.enable_walk_shaping",
  "reward_enable_upright_bonus": "reward.enable_upright_bonus",
  "reward_enable_posture_penalties": "reward.enable_posture_penalties",
  "reward_enable_double_support": "reward.enable_double_support",
  "reward_enable_flight_duration": "reward.enable_flight_duration",
  "reward_enable_effort": "reward.enable_effort",
  # 報酬係数
  "double_support_penalty_scale": "reward.double_support_penalty_scale",
  "alternating_landing_bonus_scale": "reward.alternating_landing_bonus_scale",
  "forward_reward_scale": "reward.forward_reward_scale",
  "swing_clearance_bonus_scale": "reward.swing_clearance_bonus_scale",
  "landing_bonus_scale": "reward.landing_bonus_scale",
  "push_off_bonus_scale": "reward.push_off_bonus_scale",
  "aerial_duration_penalty_after_steps": "reward.aerial_duration_penalty_after_steps",
  "forward_require_single_support": "reward.forward_require_single_support",
  "forward_imu_lean_gate": "reward.forward_imu_lean_gate",
  # 終了
  "min_imu_z": "termination.min_imu_z",
  "min_imu_z_stance": "termination.min_imu_z_stance",
  "min_imu_upright": "termination.min_imu_upright",
  "max_backward_lean_body": "termination.max_backward_lean_body",
  "pose_termination_penalty": "termination.pose_termination_penalty",
  "contact_shank_terminates": "termination.contact_shank_terminates",
  # 学習 DR / 実行
  "training_dr_enabled": "training.training_dr",
  "training_dr_pose_scale": "training.training_dr_pose_scale",
  "num_envs": "runtime.num_envs",
  # 追加キー（legacy dispatch 拡張）
  "lr": "ppo.lr",
  "num_updates": "training.num_updates",
  "wandb": "wandb.enabled",
  "seed": "training.seed",
}


def merge_dispatch_overrides(cfg: DictConfig) -> DictConfig:
  """DISPATCH_CONFIG_OVERRIDES_JSON を cfg に反映する。"""
  raw = os.environ.get("DISPATCH_CONFIG_OVERRIDES_JSON", "").strip()
  if not raw:
    return cfg

  payload = json.loads(raw)
  if not isinstance(payload, dict):
    raise ValueError("DISPATCH_CONFIG_OVERRIDES_JSON は JSON object を指定してください")

  unknown: list[str] = []
  for key, value in payload.items():
    cfg_path = DISPATCH_KEY_TO_CFG_PATH.get(str(key))
    if cfg_path is None:
      unknown.append(str(key))
      continue

    # wandb は bool 直接指定を優先。dict なら wandb.* に展開する。
    if str(key) == "wandb" and isinstance(value, dict):
      for child_key, child_val in value.items():
        OmegaConf.update(cfg, f"wandb.{child_key}", child_val, merge=False)
      continue

    OmegaConf.update(cfg, cfg_path, value, merge=False)

  if unknown:
    keys = ", ".join(sorted(unknown))
    raise ValueError(f"未対応の dispatch 上書きキー: {keys}")

  return cfg
