"""TelemetryContract から Hub 向け reset/step ペイロードを組み立てる。"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from mujoco_sim_common.kinematics import KINEMATICS

from mujoco_rl_sim.contract.spec import ObservationSlice, TelemetryContract


def actuator_names() -> list[str]:
  return list(KINEMATICS.keys())


def joint_qpos_to_logical_deg(model, data) -> list[float]:
  """各関節の qpos（rad）を論理角（deg）へ。"""
  out: list[float] = []
  for name in actuator_names():
    kin = KINEMATICS[name]
    q_rad = float(data.joint(kin.joint).qpos[0])
    mujoco_deg = float(np.rad2deg(q_rad))
    out.append(float(kin.mujoco_deg_to_logical(mujoco_deg)))
  return out


def policy_action_to_logical_deg(
  model, data, action_norm: tuple[float, ...]
) -> list[float]:
  _ = action_norm
  return joint_qpos_to_logical_deg(model, data)


def obs_vector_to_telemetry_fields(
  obs_vector: np.ndarray | list[float] | tuple[float, ...],
  contract: TelemetryContract,
  *,
  prefix: str = "",
) -> dict[str, Any]:
  """観測ベクトルを biped_ppo_v1 テレメトリフィールドに分解。"""
  o = np.asarray(obs_vector, dtype=np.float64).reshape(-1)
  if o.size != contract.observation.obs_dim:
    raise ValueError(
      f"obs_vector size {o.size} != contract obs_dim {contract.observation.obs_dim}"
    )
  out: dict[str, Any] = {f"{prefix}obs_flat": o.tolist()}
  for s in contract.observation.slices:
    key = f"{prefix}{s.telemetry_key}"
    chunk = o[s.start : s.end]
    if s.kind == "scalar":
      out[key] = float(chunk[0]) if chunk.size else 0.0
    else:
      out[key] = chunk.tolist()
  prev = _prev_action_slice(contract.observation.slices)
  if prev is not None:
    p = prefix
    prev_vals = o[prev.start : prev.end].tolist()
    out[f"{p}obs_prev_ctrl"] = prev_vals
    out[f"{p}obs_prev_action_logical_deg"] = prev_vals
    out[f"{p}obs_prev_action_unit"] = "normalized"
  return out


def _prev_action_slice(slices: tuple[ObservationSlice, ...]) -> ObservationSlice | None:
  for s in slices:
    if s.telemetry_key == "obs_prev_action_norm":
      return s
  return None


def build_reset_payload(
  contract: TelemetryContract,
  *,
  obs_vector: tuple[float, ...] | list[float],
  actuator_names_list: list[str] | None = None,
  num_timesteps: int | None = None,
  exp_name: str,
) -> dict[str, Any]:
  o = np.asarray(obs_vector, dtype=np.float64)
  names = actuator_names_list or actuator_names()
  return {
    "schema": contract.schema_id,
    "exp_name": exp_name,
    "wall_time": time.time(),
    "actuator_names": list(names),
    "obs_dim": int(o.size),
    **obs_vector_to_telemetry_fields(o, contract),
    "num_timesteps": num_timesteps,
  }


def build_step_payload(
  contract: TelemetryContract,
  *,
  obs_before: np.ndarray,
  action_norm: tuple[float, ...] | list[float],
  obs_after: np.ndarray,
  info: dict[str, Any],
  episode_step: int,
  num_timesteps: int | None,
  exp_name: str,
) -> dict[str, Any]:
  o_before = np.asarray(obs_before, dtype=np.float64)
  o_after = np.asarray(obs_after, dtype=np.float64)
  a_norm = np.asarray(action_norm, dtype=np.float64).reshape(-1)
  names = info.get("actuator_names")
  actuator_names_list = (
    [str(x) for x in names] if isinstance(names, list) else actuator_names()
  )
  a_logical = np.asarray(
    info.get("action_logical_deg", []),
    dtype=np.float64,
  ).reshape(-1)
  reward_total = float(info.get("reward_total", info.get("reward", 0.0)))
  reward_effort = float(info.get("reward_effort_penalty", 0.0))
  reward_fall = float(info.get("reward_fall_penalty", 0.0))
  torso_height = info.get("torso_height")
  torso_height_num = (
    float(torso_height) if isinstance(torso_height, (float, int)) else None
  )
  step_wall_sleep = info.get("step_wall_sleep_sec")
  step_wall_sleep_num = (
    float(step_wall_sleep) if isinstance(step_wall_sleep, (float, int)) else None
  )
  payload: dict[str, Any] = {
    "schema": contract.schema_id,
    "exp_name": exp_name,
    "wall_time": time.time(),
    "episode_step": int(episode_step),
    "num_timesteps": num_timesteps,
    "actuator_names": actuator_names_list,
    "action": a_norm.tolist(),
    "action_norm": a_norm.tolist(),
    "action_norm_unit": "normalized",
    "action_logical_deg": a_logical.tolist(),
    "action_unit": "logical_deg",
    "reward": reward_total,
    "reward_total": reward_total,
    "reward_effort_penalty": reward_effort,
    "reward_fall_penalty": reward_fall,
    "torso_height": torso_height_num,
    "step_wall_sleep_sec": step_wall_sleep_num,
    "is_fallen": bool(info.get("is_fallen", False)),
    "terminated": bool(info.get("terminated", False)),
    "truncated": bool(info.get("truncated", False)),
    **obs_vector_to_telemetry_fields(o_before, contract, prefix=""),
    **obs_vector_to_telemetry_fields(o_after, contract, prefix="obs_next_"),
  }
  if contract.include_legacy_gyro_alias:
    if "obs_imu_gyro" in payload:
      payload["obs_gyro"] = payload["obs_imu_gyro"]
    if "obs_next_imu_gyro" in payload:
      payload["obs_next_gyro"] = payload["obs_next_imu_gyro"]
  return payload
