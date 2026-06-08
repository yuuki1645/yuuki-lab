"""両脚バイペッド PPO 向け Hub テレメトリ（契約 ``biped_ppo_v1`` の薄いラッパ）。"""

from __future__ import annotations

from typing import Any

import numpy as np

from contract.biped_v1 import BIPED_PPO_V1
from contract.telemetry import (
  actuator_names,
  build_reset_payload as _build_reset_payload,
  build_step_payload as _build_step_payload,
  joint_qpos_to_logical_deg,
  policy_action_to_logical_deg,
)
from mujoco_sim_common.kinematics import KINEMATICS

from telemetry.env_wrapper import RlTelemetryWrapper

EXP_SCHEMA = BIPED_PPO_V1.schema_id
_CONTRACT = BIPED_PPO_V1


def build_reset_payload(
  *,
  obs_vector: tuple[float, ...] | list[float],
  actuator_names_list: list[str] | None = None,
  num_timesteps: int | None = None,
  exp_name: str,
) -> dict[str, Any]:
  return _build_reset_payload(
    _CONTRACT,
    obs_vector=obs_vector,
    actuator_names_list=actuator_names_list,
    num_timesteps=num_timesteps,
    exp_name=exp_name,
  )


def build_step_payload(
  *,
  obs_before: np.ndarray,
  action_norm: tuple[float, ...] | list[float],
  obs_after: np.ndarray,
  info: dict[str, Any],
  episode_step: int,
  num_timesteps: int | None,
  exp_name: str,
) -> dict[str, Any]:
  return _build_step_payload(
    _CONTRACT,
    obs_before=obs_before,
    action_norm=action_norm,
    obs_after=obs_after,
    info=info,
    episode_step=episode_step,
    num_timesteps=num_timesteps,
    exp_name=exp_name,
  )


__all__ = [
  "EXP_SCHEMA",
  "RlTelemetryWrapper",
  "actuator_names",
  "build_reset_payload",
  "build_step_payload",
  "joint_qpos_to_logical_deg",
  "policy_action_to_logical_deg",
]
