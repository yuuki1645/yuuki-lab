"""exp_019 系（両脚バイペッド PPO）向け Hub テレメトリペイロード構築。"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from mujoco_sim_common.kinematics import KINEMATICS

from .env_wrapper import RlTelemetryWrapper

EXP_SCHEMA = "biped_ppo_v1"


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


def policy_action_to_logical_deg(model, data, action_norm: tuple[float, ...]) -> list[float]:
    """正規化 action [-1,1] から論理角（deg）を推定（ctrl 適用後の qpos を優先）。"""
    _ = action_norm
    return joint_qpos_to_logical_deg(model, data)


def build_reset_payload(
    *,
    obs_vector: tuple[float, ...] | list[float],
    actuator_names_list: list[str] | None = None,
    num_timesteps: int | None = None,
    exp_name: str,
) -> dict[str, Any]:
    o = np.asarray(obs_vector, dtype=np.float64)
    names = actuator_names_list or actuator_names()
    return {
        "schema": EXP_SCHEMA,
        "exp_name": exp_name,
        "wall_time": time.time(),
        "actuator_names": list(names),
        "obs_dim": int(o.size),
        "obs_flat": o.tolist(),
        "num_timesteps": num_timesteps,
        **_obs_slices(o),
    }


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
        "schema": EXP_SCHEMA,
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
        **_obs_slices(o_before, prefix=""),
        **_obs_slices(o_after, prefix="obs_next_"),
    }
    # 後方互換: 旧 Hub が obs_acc / obs_gyro を参照する場合のエイリアス
    if "obs_imu_gyro" in payload:
        payload["obs_gyro"] = payload["obs_imu_gyro"]
    if "obs_next_imu_gyro" in payload:
        payload["obs_next_gyro"] = payload["obs_next_imu_gyro"]
    return payload


def _obs_slices(o: np.ndarray, *, prefix: str = "") -> dict[str, Any]:
    """42 次元 PolicyObs ベクトルをテレメトリ用フィールドに分解。"""
    p = prefix
    n = int(o.size)
    joint_q_start = 12
    joint_qvel_start = 22
    prev_start = 32
    joint_q = o[joint_q_start:joint_qvel_start].tolist() if n >= joint_qvel_start else []
    joint_qvel = o[joint_qvel_start:prev_start].tolist() if n >= prev_start else []
    prev_action = o[prev_start:42].tolist() if n >= 42 else o[prev_start:].tolist()
    return {
        f"{p}obs_dx": float(o[0]) if n > 0 else 0.0,
        f"{p}obs_imu_gyro": o[1:4].tolist() if n >= 4 else [],
        f"{p}obs_imu_zaxis": o[4:7].tolist() if n >= 7 else [],
        f"{p}obs_imu_z_norm": float(o[7]) if n > 7 else 0.0,
        f"{p}obs_left_foot_contact": float(o[8]) if n > 8 else 0.0,
        f"{p}obs_right_foot_contact": float(o[9]) if n > 9 else 0.0,
        f"{p}obs_left_foot_dx": float(o[10]) if n > 10 else 0.0,
        f"{p}obs_right_foot_dx": float(o[11]) if n > 11 else 0.0,
        f"{p}obs_joint_q_norm": joint_q,
        f"{p}obs_joint_qvel_norm": joint_qvel,
        f"{p}obs_prev_action_norm": prev_action,
        f"{p}obs_prev_action_unit": "normalized",
        f"{p}obs_flat": o.tolist(),
        # 旧クライアント互換（末尾 prev は正規化 action）
        f"{p}obs_prev_ctrl": prev_action,
        f"{p}obs_prev_action_logical_deg": prev_action,
    }


__all__ = [
    "EXP_SCHEMA",
    "RlTelemetryWrapper",
    "actuator_names",
    "build_reset_payload",
    "build_step_payload",
    "joint_qpos_to_logical_deg",
    "policy_action_to_logical_deg",
]
