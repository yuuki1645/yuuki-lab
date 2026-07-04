# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Reset events for the biped walk task."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedEnv

from .episode_state import get_biped_state


def reset_robot_to_default(
    env: ManagerBasedEnv,
    env_ids: torch.Tensor,
    asset_name: str = "robot",
) -> None:
    """Write default stand keyframe to sim and set joint position targets."""
    robot = env.scene[asset_name]
    joint_pos = robot.data.default_joint_pos[env_ids]
    joint_vel = robot.data.default_joint_vel[env_ids]
    default_root_state = robot.data.default_root_state[env_ids].clone()
    default_root_state[:, :3] += env.scene.env_origins[env_ids]

    robot.write_root_pose_to_sim(default_root_state[:, :7], env_ids)
    robot.write_root_velocity_to_sim(default_root_state[:, 7:], env_ids)
    robot.write_joint_state_to_sim(joint_pos, joint_vel, None, env_ids)

    state = get_biped_state(env)
    robot.set_joint_position_target(joint_pos[:, state.joint_ids], joint_ids=state.joint_ids, env_ids=env_ids)

    env.scene.write_data_to_sim()
    env.sim.forward()


def apply_reset_joint_noise(
    env: ManagerBasedEnv,
    env_ids: torch.Tensor,
    asset_name: str = "robot",
    noise_rad: float = 0.010,
) -> None:
    """Apply uniform joint-angle noise after the default reset pose."""
    if noise_rad <= 0.0:
        return

    robot = env.scene[asset_name]
    state = get_biped_state(env)
    joint_pos = robot.data.joint_pos[env_ids].clone()
    joint_vel = robot.data.joint_vel[env_ids].clone()
    noisy = joint_pos[:, state.joint_ids] + (torch.rand_like(joint_pos[:, state.joint_ids]) * 2.0 - 1.0) * noise_rad
    noisy = torch.clamp(noisy, state.joint_lo.unsqueeze(0), state.joint_hi.unsqueeze(0))
    joint_pos[:, state.joint_ids] = noisy
    robot.write_joint_state_to_sim(joint_pos, joint_vel, None, env_ids)
    robot.set_joint_position_target(noisy, joint_ids=state.joint_ids, env_ids=env_ids)
