# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Step reward (wraps Direct compute_step_reward as a Manager term)."""

from __future__ import annotations

import torch
from isaaclab.envs import ManagerBasedRLEnv

from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import action as action_mdp
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import reward as reward_mdp
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import termination as termination_mdp
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.biped_ppo_walk_env_cfg import BipedPpoWalkEnvCfg, get_max_dx_per_step

from .episode_state import ensure_step_updated, get_biped_state


def _update_pose_hysteresis(env: ManagerBasedRLEnv, physics: dict[str, torch.Tensor]) -> torch.Tensor:
    """Update consecutive bad-pose counter; return post-update termination flag."""
    state = get_biped_state(env)
    term_cfg = env.cfg.termination
    pose_bad, _ = termination_mdp.compute_pose_termination(
        imu_z=physics["imu_z"],
        upright=physics["upright"],
        lean_fwd_body=physics["lean_fwd_body"],
        both_feet_on_floor=physics["left_on_floor"] & physics["right_on_floor"],
        min_imu_z=term_cfg.min_imu_z,
        min_imu_upright=term_cfg.min_imu_upright,
        max_backward_lean_body=term_cfg.max_backward_lean_body,
        max_forward_lean_both_feet=term_cfg.max_forward_lean_both_feet,
        pose_termination_penalty=term_cfg.pose_termination_penalty,
    )
    state.bad_pose_steps = torch.where(
        pose_bad,
        state.bad_pose_steps + 1,
        torch.zeros_like(state.bad_pose_steps),
    )
    return state.bad_pose_steps >= term_cfg.bad_pose_consecutive_steps


def step_reward(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Per-step total reward (same as Direct _get_rewards)."""
    snap = ensure_step_updated(env)
    state = get_biped_state(env)
    physics = snap.physics
    biped = snap.biped
    cfg: BipedPpoWalkEnvCfg = env.cfg  # type: ignore[assignment]

    pose_done = _update_pose_hysteresis(env, physics)

    robot = env.scene["robot"]
    effort_penalty = reward_mdp.compute_effort_penalty(
        robot.data.applied_torque[:, state.joint_ids],
        robot.data.joint_vel[:, state.joint_ids],
        dt=cfg.sim.dt * float(cfg.decimation),
        scale=cfg.reward.effort_penalty_scale,
    )

    reward, forward, effort, state.milestone_level, state.survival_milestone_level = reward_mdp.compute_step_reward(
        cfg=cfg.reward,
        max_dx_per_step=get_max_dx_per_step(cfg),
        dx=snap.dx,
        root_vel_x=physics["root_vel_x"],
        left_foot_dx=snap.left_foot_dx,
        right_foot_dx=snap.right_foot_dx,
        upright=physics["upright"],
        lean_fwd_body=physics["lean_fwd_body"],
        heading_align=physics["heading_align"],
        tilt_horiz=physics["tilt_horiz"],
        imu_z=physics["imu_z"],
        left_foot_z=physics["left_foot_z"],
        right_foot_z=physics["right_foot_z"],
        left_knee=physics["left_knee"],
        right_knee=physics["right_knee"],
        biped=biped,
        progress_m=snap.progress_m,
        imu_dz=snap.imu_dz,
        left_knee_vel=physics["left_knee_vel"],
        right_knee_vel=physics["right_knee_vel"],
        left_toe_z=physics["left_toe_z"],
        left_heel_z=physics["left_heel_z"],
        right_toe_z=physics["right_toe_z"],
        right_heel_z=physics["right_heel_z"],
        effort_penalty=effort_penalty,
        imu_gyro=physics["imu_gyro"],
        root_vel_y=physics["root_vel_y"],
        episode_step=env.episode_length_buf,
        max_episode_steps=env.max_episode_length,
        total_displacement=physics["imu_x"] - state.episode_start_imu_x,
        milestone_level=state.milestone_level,
        survival_milestone_level=state.survival_milestone_level,
        current_action=action_mdp.clip_policy_action(env.action_manager.action),
        prev_step_action=state.prev_step_action,
    )

    env.extras.setdefault("log", {})
    env.extras["log"].update(
        {
            "Reward/mean_forward": forward.mean(),
            "Reward/mean_effort": effort.mean(),
            "Metrics/mean_imu_x": physics["imu_x"].mean(),
            "Metrics/mean_root_vel_x": physics["root_vel_x"].mean(),
            "Metrics/mean_upright": physics["upright"].mean(),
            "Metrics/mean_imu_z": physics["imu_z"].mean(),
            "Metrics/left_contact_ratio": physics["left_on_floor"].float().mean(),
            "Metrics/right_contact_ratio": physics["right_on_floor"].float().mean(),
            "Metrics/single_support_ratio": biped.single_support.float().mean(),
            "Metrics/mean_left_foot_z": physics["left_foot_z"].mean(),
            "Metrics/mean_right_foot_z": physics["right_foot_z"].mean(),
            "Metrics/term_low_z_ratio": (physics["imu_z"] < cfg.termination.min_imu_z).float().mean(),
            "Metrics/term_low_upright_ratio": (physics["upright"] < cfg.termination.min_imu_upright).float().mean(),
            "Metrics/mean_lean_fwd": physics["lean_fwd_body"].mean(),
            "Metrics/both_feet_ratio": (physics["left_on_floor"] & physics["right_on_floor"]).float().mean(),
            "Metrics/mean_same_side_streak": biped.same_side_streak.float().mean(),
            "Metrics/alternating_landing_ratio": biped.alternating_landing.float().mean(),
            "Metrics/right_single_support_ratio": (
                biped.single_support & (biped.single_support_side == -1)
            ).float().mean(),
            "Metrics/foot_swap_ratio": biped.foot_swap.float().mean(),
            "Metrics/mean_milestone_level": state.milestone_level.float().mean(),
            "Metrics/mean_survival_milestone_level": state.survival_milestone_level.float().mean(),
            "Metrics/mean_bad_pose_steps": state.bad_pose_steps.float().mean(),
        }
    )

    _, pose_penalty = termination_mdp.compute_pose_termination(
        imu_z=physics["imu_z"],
        upright=physics["upright"],
        lean_fwd_body=physics["lean_fwd_body"],
        both_feet_on_floor=physics["left_on_floor"] & physics["right_on_floor"],
        min_imu_z=cfg.termination.min_imu_z,
        min_imu_upright=cfg.termination.min_imu_upright,
        max_backward_lean_body=cfg.termination.max_backward_lean_body,
        max_forward_lean_both_feet=cfg.termination.max_forward_lean_both_feet,
        pose_termination_penalty=cfg.termination.pose_termination_penalty,
    )
    terminal_penalty = torch.where(pose_done, pose_penalty, torch.zeros_like(reward))
    
    return reward + terminal_penalty
