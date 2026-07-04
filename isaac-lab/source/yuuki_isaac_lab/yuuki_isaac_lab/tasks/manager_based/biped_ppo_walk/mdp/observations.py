# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""54-dim policy observation (same layout as Direct _get_observations)."""

from __future__ import annotations

import torch
from isaaclab.envs import ManagerBasedRLEnv

from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import obs_norm
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.biped_ppo_walk_env_cfg import (
    BipedPpoWalkEnvCfg,
    get_max_dx_per_step,
    get_max_foot_dx_per_step,
)

from .episode_state import ensure_step_updated, get_biped_state


def policy_obs(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Build 54-dim observation vector [num_envs, 54]."""
    snap = ensure_step_updated(env)
    state = get_biped_state(env)
    physics = snap.physics
    biped = snap.biped
    cfg: BipedPpoWalkEnvCfg = env.cfg  # type: ignore[assignment]

    robot = env.scene["robot"]
    joint_q = robot.data.joint_pos[:, state.joint_ids]
    joint_qvel = robot.data.joint_vel[:, state.joint_ids]
    joint_q_norm = obs_norm.range_to_norm(joint_q, state.joint_lo, state.joint_hi)
    joint_qvel_norm = obs_norm.clip_scale(joint_qvel, cfg.max_joint_vel_rad_s)

    dx = snap.dx
    support_side_obs = biped.single_support_side.float().unsqueeze(-1)
    streak_norm = torch.clamp(biped.same_side_streak.float() / 40.0, max=1.0).unsqueeze(-1)
    ep_progress = (env.episode_length_buf.float() / float(env.max_episode_length)).unsqueeze(-1)

    obs = torch.cat(
        [
            obs_norm.clip_scale(dx, get_max_dx_per_step(cfg)).unsqueeze(-1),
            obs_norm.clip_scale(physics["imu_gyro"], cfg.max_gyro_rad_s),
            physics["imu_zaxis"],
            obs_norm.height_to_norm(physics["imu_z"], cfg.min_imu_z_norm, cfg.max_imu_z).unsqueeze(-1),
            torch.where(physics["left_on_floor"], torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1),
            torch.where(physics["right_on_floor"], torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1),
            obs_norm.clip_scale(snap.left_foot_dx, get_max_foot_dx_per_step(cfg)).unsqueeze(-1),
            obs_norm.clip_scale(snap.right_foot_dx, get_max_foot_dx_per_step(cfg)).unsqueeze(-1),
            obs_norm.height_to_norm(physics["left_foot_z"], cfg.min_foot_z_norm, cfg.max_foot_z_norm).unsqueeze(-1),
            obs_norm.height_to_norm(physics["right_foot_z"], cfg.min_foot_z_norm, cfg.max_foot_z_norm).unsqueeze(-1),
            torch.where(biped.single_support, torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1),
            joint_q_norm,
            joint_qvel_norm,
            state.prev_action,
            support_side_obs,
            streak_norm,
            ep_progress,
        ],
        dim=-1,
    )
    return obs
