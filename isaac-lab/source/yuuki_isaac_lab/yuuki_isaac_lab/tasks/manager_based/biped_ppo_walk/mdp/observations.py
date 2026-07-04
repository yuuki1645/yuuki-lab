# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Manager-based observation terms (54-dim policy group when concatenated)."""

from __future__ import annotations

import torch
from isaaclab.envs import ManagerBasedRLEnv
from isaaclab.managers import SceneEntityCfg

from . import obs_norm
from .actuators import JOINT_NAMES
from .env_params import get_max_dx_per_step, get_max_foot_dx_per_step
from .episode_state import ensure_step_updated, get_biped_state


def _obs_cfg(env: ManagerBasedRLEnv):
    """Return observation normalization config attached to the environment."""
    return env.cfg.observation_params  # type: ignore[attr-defined]


def _snap(env: ManagerBasedRLEnv):
    """Ensure gait snapshot exists before reading observation terms."""
    snap = ensure_step_updated(env)
    state = get_biped_state(env)
    return snap, state


def imu_dx(env: ManagerBasedRLEnv) -> torch.Tensor:
    """IMU +X displacement since last control step [num_envs, 1]."""
    snap, _ = _snap(env)
    cfg = _obs_cfg(env)
    return obs_norm.clip_scale(snap.dx, get_max_dx_per_step(cfg, env.cfg.decimation)).unsqueeze(-1)


def imu_gyro(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Root angular velocity (gyro proxy) [num_envs, 3]."""
    snap, _ = _snap(env)
    cfg = _obs_cfg(env)
    return obs_norm.clip_scale(snap.physics["imu_gyro"], cfg.max_gyro_rad_s)


def imu_zaxis(env: ManagerBasedRLEnv) -> torch.Tensor:
    """IMU up axis in world frame [num_envs, 3]."""
    snap, _ = _snap(env)
    return snap.physics["imu_zaxis"]


def imu_height(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Normalized IMU height [num_envs, 1]."""
    snap, _ = _snap(env)
    cfg = _obs_cfg(env)
    return obs_norm.height_to_norm(snap.physics["imu_z"], cfg.min_imu_z_norm, cfg.max_imu_z).unsqueeze(-1)


def left_foot_contact(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Left foot contact flag in {-1, +1} [num_envs, 1]."""
    snap, _ = _snap(env)
    dx = snap.dx
    on = snap.physics["left_on_floor"]
    return torch.where(on, torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1)


def right_foot_contact(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Right foot contact flag in {-1, +1} [num_envs, 1]."""
    snap, _ = _snap(env)
    dx = snap.dx
    on = snap.physics["right_on_floor"]
    return torch.where(on, torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1)


def left_foot_dx(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Left foot +X displacement [num_envs, 1]."""
    snap, _ = _snap(env)
    cfg = _obs_cfg(env)
    return obs_norm.clip_scale(snap.left_foot_dx, get_max_foot_dx_per_step(cfg, env.cfg.decimation)).unsqueeze(-1)


def right_foot_dx(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Right foot +X displacement [num_envs, 1]."""
    snap, _ = _snap(env)
    cfg = _obs_cfg(env)
    return obs_norm.clip_scale(snap.right_foot_dx, get_max_foot_dx_per_step(cfg, env.cfg.decimation)).unsqueeze(-1)


def left_foot_height(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Normalized left foot height [num_envs, 1]."""
    snap, _ = _snap(env)
    cfg = _obs_cfg(env)
    return obs_norm.height_to_norm(snap.physics["left_foot_z"], cfg.min_foot_z_norm, cfg.max_foot_z_norm).unsqueeze(-1)


def right_foot_height(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Normalized right foot height [num_envs, 1]."""
    snap, _ = _snap(env)
    cfg = _obs_cfg(env)
    return obs_norm.height_to_norm(snap.physics["right_foot_z"], cfg.min_foot_z_norm, cfg.max_foot_z_norm).unsqueeze(-1)


def single_support_flag(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Single-support flag in {-1, +1} [num_envs, 1]."""
    snap, _ = _snap(env)
    dx = snap.dx
    return torch.where(snap.biped.single_support, torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1)


def joint_pos_normalized(
    env: ManagerBasedRLEnv,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot", joint_names=list(JOINT_NAMES)),
) -> torch.Tensor:
    """Joint positions mapped to [-1, 1] [num_envs, 12]."""
    _, state = _snap(env)
    robot = env.scene[asset_cfg.name]
    joint_ids = state.joint_ids
    joint_q = robot.data.joint_pos[:, joint_ids]
    return obs_norm.range_to_norm(joint_q, state.joint_lo, state.joint_hi)


def joint_vel_normalized(
    env: ManagerBasedRLEnv,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot", joint_names=list(JOINT_NAMES)),
) -> torch.Tensor:
    """Joint velocities clipped to [-1, 1] [num_envs, 12]."""
    _, state = _snap(env)
    cfg = _obs_cfg(env)
    robot = env.scene[asset_cfg.name]
    joint_ids = state.joint_ids
    joint_qvel = robot.data.joint_vel[:, joint_ids]
    return obs_norm.clip_scale(joint_qvel, cfg.max_joint_vel_rad_s)


def last_action(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Previous clipped policy action [num_envs, 12]."""
    _, state = _snap(env)
    return state.prev_action


def support_side(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Single-support side (-1 right, 0 none, +1 left) [num_envs, 1]."""
    snap, _ = _snap(env)
    return snap.biped.single_support_side.float().unsqueeze(-1)


def same_side_streak_normalized(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Same-side support streak normalized to [0, 1] [num_envs, 1]."""
    snap, _ = _snap(env)
    cfg = _obs_cfg(env)
    streak_norm = torch.clamp(snap.biped.same_side_streak.float() / cfg.same_side_streak_norm_steps, max=1.0)
    return streak_norm.unsqueeze(-1)


def episode_progress(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Episode progress fraction [num_envs, 1]."""
    progress = env.episode_length_buf.float() / float(env.max_episode_length)
    return progress.unsqueeze(-1)
