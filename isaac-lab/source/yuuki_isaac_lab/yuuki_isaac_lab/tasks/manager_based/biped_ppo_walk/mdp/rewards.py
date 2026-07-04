# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Manager-based reward terms for biped alternating walk (+X).

Each function returns an unweighted reward contribution; scales are applied via
``RewardTermCfg.weight`` in ``biped_ppo_walk_env_cfg.py``.
"""

from __future__ import annotations

import torch
from isaaclab.envs import ManagerBasedRLEnv

from . import termination as termination_mdp
from .episode_state import ensure_step_updated, get_biped_state
from .reward_utils import compute_milestone_bonus


def _snap(env: ManagerBasedRLEnv):
    """Ensure step snapshot exists and return (snap, state, walk_params)."""
    snap = ensure_step_updated(env)
    state = get_biped_state(env)
    return snap, state, env.cfg.walk_params  # type: ignore[attr-defined]


# --- Primary forward terms ---


def forward_imu(env: ManagerBasedRLEnv) -> torch.Tensor:
    """IMU +X displacement reward during allowed single-support forward motion."""
    snap, _, params = _snap(env)
    dx = snap.dx
    max_dx = snap.max_dx_per_step
    dx_clipped = torch.clamp(dx, -max_dx, max_dx)
    return torch.where(
        snap.forward_allowed & (dx_clipped >= params.forward_min_dx),
        torch.clamp(dx_clipped, min=0.0),
        torch.zeros_like(dx),
    )


def forward_velocity(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Root +X velocity reward during forward-allowed phases."""
    snap, _, params = _snap(env)
    vel = torch.clamp(snap.physics["root_vel_x"], min=0.0, max=params.forward_vel_max)
    return torch.where(snap.forward_allowed, vel, torch.zeros_like(vel))


def forward_foot(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Stance-foot +X displacement reward (left stance by default)."""
    snap, _, params = _snap(env)
    biped = snap.biped
    dx = snap.dx
    max_dx = snap.max_dx_per_step

    stance_foot_dx = torch.zeros_like(dx)
    stance_foot_dx = torch.where(
        biped.single_support & (biped.single_support_side == 1),
        torch.clamp(snap.left_foot_dx, min=0.0),
        stance_foot_dx,
    )
    if not params.forward_foot_left_stance_only:
        stance_foot_dx = torch.where(
            biped.single_support & (biped.single_support_side == -1),
            torch.clamp(snap.right_foot_dx, min=0.0),
            stance_foot_dx,
        )
    foot_dx_clipped = torch.clamp(stance_foot_dx, -max_dx, max_dx)
    return torch.where(
        snap.forward_allowed & (foot_dx_clipped >= params.forward_min_dx),
        foot_dx_clipped,
        torch.zeros_like(dx),
    )


def progress(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Episode IMU +X progress increment."""
    snap, _, _ = _snap(env)
    return torch.where(snap.shaping_allowed, snap.progress_m, torch.zeros_like(snap.dx))


# --- Gait shaping bonuses ---


def upright_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    bonus = torch.clamp(snap.physics["upright"] - params.upright_bonus_thresh, min=0.0)
    return torch.where(
        snap.shaping_allowed & (snap.dx >= params.upright_bonus_min_dx),
        bonus,
        torch.zeros_like(bonus),
    )


def push_off_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    physics = snap.physics
    foot_dx_ss = torch.where(
        biped.single_support_side == 1,
        snap.left_foot_dx,
        torch.where(biped.single_support_side == -1, snap.right_foot_dx, snap.dx),
    )
    knee_vel_ss = torch.where(
        biped.single_support_side == 1,
        physics["left_knee_vel"],
        torch.where(biped.single_support_side == -1, physics["right_knee_vel"], snap.dx),
    )
    push_ok = snap.shaping_allowed & biped.single_support & (foot_dx_ss >= params.push_off_min_foot_dx)
    push_ok = push_ok & ((knee_vel_ss < -params.push_off_min_knee_ext_vel) | (snap.imu_dz >= params.push_off_min_imu_dz))
    return torch.where(push_ok, torch.ones_like(snap.dx), torch.zeros_like(snap.dx))


def landing_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    physics = snap.physics
    toe_z = torch.where(biped.left_landed, physics["left_toe_z"], torch.where(biped.right_landed, physics["right_toe_z"], snap.dx))
    heel_z = torch.where(biped.left_landed, physics["left_heel_z"], torch.where(biped.right_landed, physics["right_heel_z"], snap.dx))
    land_ok = snap.shaping_allowed & (biped.left_landed | biped.right_landed)
    land_ok = land_ok & (toe_z <= params.landing_max_toe_z) & (heel_z <= params.landing_max_heel_z)
    land_ok = land_ok & (physics["lean_fwd_body"] <= params.landing_max_forward_lean)
    return torch.where(land_ok, torch.ones_like(snap.dx), torch.zeros_like(snap.dx))


def alternating_landing_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, _ = _snap(env)
    return torch.where(
        snap.shaping_allowed & snap.biped.alternating_landing,
        torch.ones_like(snap.dx),
        torch.zeros_like(snap.dx),
    )


def left_landing_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    physics = snap.physics
    left_land_ok = snap.shaping_allowed & biped.left_landed
    left_land_ok = left_land_ok & (physics["left_toe_z"] <= params.landing_max_toe_z)
    left_land_ok = left_land_ok & (physics["left_heel_z"] <= params.landing_max_heel_z)
    return torch.where(left_land_ok, torch.ones_like(snap.dx), torch.zeros_like(snap.dx))


def left_single_support_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    lss_ok = snap.shaping_allowed & biped.single_support & (biped.single_support_side == 1)
    lss_ok = lss_ok & (snap.dx >= params.left_single_support_min_dx)
    return torch.where(lss_ok, torch.ones_like(snap.dx), torch.zeros_like(snap.dx))


def foot_swap_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, _ = _snap(env)
    return torch.where(
        snap.shaping_allowed & snap.biped.foot_swap,
        torch.ones_like(snap.dx),
        torch.zeros_like(snap.dx),
    )


def swing_clearance_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    physics = snap.physics
    swing_z = torch.where(
        biped.single_support & (biped.single_support_side == 1) & (~biped.right_landed),
        physics["right_foot_z"],
        torch.where(
            biped.single_support & (biped.single_support_side == -1) & (~biped.left_landed),
            physics["left_foot_z"],
            snap.dx,
        ),
    )
    clearance = torch.clamp(swing_z - params.swing_min_foot_z, min=0.0)
    return torch.where(snap.shaping_allowed & biped.single_support, clearance, torch.zeros_like(clearance))


def duration_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    physics = snap.physics
    dur_frac = env.episode_length_buf.float() / float(env.max_episode_length)
    dur_ok = (physics["upright"] >= params.alive_min_upright) & (snap.dx >= params.shaping_min_dx)
    return torch.where(dur_ok, dur_frac, torch.zeros_like(dur_frac))


def displacement_milestone_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, state, params = _snap(env)
    bonus, state.milestone_level = compute_milestone_bonus(
        snap.total_displacement,
        state.milestone_level,
        params.displacement_milestone_targets,
        params.displacement_milestone_scales,
    )
    return bonus


def survival_milestone_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, state, params = _snap(env)
    bonus, state.survival_milestone_level = compute_milestone_bonus(
        env.episode_length_buf.float(),
        state.survival_milestone_level,
        tuple(float(t) for t in params.survival_milestone_targets),
        params.survival_milestone_scales,
    )
    return bonus


def alive_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    physics = snap.physics
    alive_ok = (physics["upright"] >= params.alive_min_upright) & (physics["imu_z"] >= params.alive_min_imu_z)
    alive_scale = torch.ones_like(snap.dx)
    alive_scale = alive_scale * (1.0 + env.episode_length_buf.float() / float(env.max_episode_length))
    return torch.where(alive_ok, alive_scale, torch.zeros_like(alive_scale))


def displacement_progress_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    disp_ok = snap.forward_allowed & (snap.total_displacement > 0.0)
    progress = torch.clamp(snap.total_displacement, min=0.0, max=15.0)
    return torch.where(disp_ok, progress, torch.zeros_like(progress))


def long_horizon_bonus(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    lh_ok = snap.forward_allowed & (env.episode_length_buf > params.long_horizon_step_threshold)
    lh_ok = lh_ok & (snap.dx >= params.shaping_min_dx)
    step_over = (env.episode_length_buf.float() - float(params.long_horizon_step_threshold)).clamp(min=0.0)
    return torch.where(lh_ok, step_over / 400.0, torch.zeros_like(step_over))


# --- Posture / gait penalties (return positive magnitudes; use negative weights) ---


def backward_lean_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    return torch.clamp(-snap.physics["lean_fwd_body"] - params.lean_backward_thresh, min=0.0)


def forward_lean_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    return torch.where(
        (~biped.any_foot_on_floor) & (biped.aerial_steps >= params.lean_forward_min_aerial_steps),
        torch.clamp(snap.physics["lean_fwd_body"] - params.lean_forward_thresh, min=0.0),
        torch.zeros_like(snap.dx),
    )


def double_support_forward_lean_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    return torch.where(
        snap.biped.both_feet_on_floor,
        torch.clamp(snap.physics["lean_fwd_body"] - params.ds_forward_lean_thresh, min=0.0),
        torch.zeros_like(snap.dx),
    )


def fall_forward_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    physics = snap.physics
    fall_hack = biped.both_feet_on_floor & (physics["lean_fwd_body"] > params.fall_forward_lean_thresh)
    return torch.where(
        fall_hack,
        torch.clamp(physics["lean_fwd_body"] - params.fall_forward_lean_thresh, min=0.0)
        + torch.clamp(snap.dx, min=0.0),
        torch.zeros_like(snap.dx),
    )


def same_side_streak_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    over_streak = snap.biped.same_side_streak.float() - float(params.same_side_streak_penalty_after)
    return torch.where(over_streak > 0.0, over_streak, torch.zeros_like(over_streak))


def contact_imbalance_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    streak_over = biped.same_side_streak.float() - float(params.contact_imbalance_streak_after)
    return torch.where(
        biped.single_support & (streak_over > 0.0),
        streak_over,
        torch.zeros_like(streak_over),
    )


def right_pivot_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    right_pivot = biped.single_support & (biped.single_support_side == -1)
    streak_over = biped.same_side_streak.float() - float(params.right_pivot_streak_after)
    return torch.where(right_pivot & (streak_over > 0.0), streak_over, torch.zeros_like(streak_over))


def backward_dx_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    return torch.where(
        (snap.physics["upright"] >= params.forward_min_upright) & (snap.dx < -params.backward_dx_thresh),
        -snap.dx,
        torch.zeros_like(snap.dx),
    )


def lateral_velocity_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, _ = _snap(env)
    return torch.abs(snap.physics["root_vel_y"])


def angular_velocity_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    penalty = torch.norm(snap.physics["imu_gyro"], dim=-1)
    return torch.where(snap.physics["upright"] >= params.alive_min_upright, penalty, torch.zeros_like(penalty))


def action_rate_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, state, _ = _snap(env)
    current = state.prev_action
    previous = state.prev_step_action
    return torch.sum(torch.abs(current - previous), dim=-1)


def imu_height_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    physics = snap.physics
    imu_z = physics["imu_z"]

    target_z = torch.full_like(imu_z, params.target_imu_z)
    target_z = torch.where(biped.single_support, torch.full_like(imu_z, params.target_imu_z_single_stance), target_z)
    target_z = torch.where(biped.both_feet_on_floor, torch.full_like(imu_z, params.target_imu_z_double_stance), target_z)
    height_penalty = torch.clamp(target_z - imu_z, min=0.0)
    return torch.where(
        ~biped.any_foot_on_floor,
        torch.where(
            imu_z < params.height_penalty_aerial_crash_z,
            torch.clamp(params.target_imu_z - imu_z, min=0.0) * 1.5,
            torch.clamp(params.target_imu_z - imu_z, min=0.0),
        ),
        height_penalty,
    )


def flight_duration_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    over = biped.aerial_steps.float() - float(params.aerial_duration_penalty_after_steps)
    return torch.where((~biped.any_foot_on_floor) & (over > 0.0), over, torch.zeros_like(over))


def knee_hyperflex_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    physics = snap.physics
    biped = snap.biped
    knee = torch.maximum(physics["left_knee"], physics["right_knee"])
    penalty = torch.clamp(knee - params.knee_hyperflex_max_rad, min=0.0)
    if params.knee_hyperflex_aerial_only:
        penalty = torch.where(biped.any_foot_on_floor, torch.zeros_like(penalty), penalty)
    return penalty


def heading_misalign_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    return torch.clamp(params.heading_align_min - snap.physics["heading_align"], min=0.0)


def lateral_tilt_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    return torch.clamp(snap.physics["tilt_horiz"] - params.lateral_tilt_thresh, min=0.0)


def double_support_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    snap, _, params = _snap(env)
    biped = snap.biped
    forward_motion = torch.maximum(
        torch.clamp(snap.dx, min=0.0),
        torch.maximum(torch.clamp(snap.left_foot_dx, min=0.0), torch.clamp(snap.right_foot_dx, min=0.0)),
    )
    return torch.where(
        biped.both_feet_on_floor,
        0.5 + torch.where(
            forward_motion < params.double_support_min_forward,
            torch.zeros_like(snap.dx),
            forward_motion,
        ),
        torch.zeros_like(snap.dx),
    )


def effort_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Precomputed in episode snapshot (positive magnitude)."""
    snap, _, _ = _snap(env)
    return snap.effort_penalty


def pose_termination_penalty(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Terminal penalty when bad-pose hysteresis triggers termination this step."""
    ensure_step_updated(env)
    state = get_biped_state(env)
    term_cfg = env.cfg.termination_params  # type: ignore[attr-defined]
    physics = state._last_physics
    biped = state._last_biped_ctx
    if physics is None or biped is None:
        return torch.zeros(env.num_envs, device=env.device)

    pose_done = state.bad_pose_steps >= term_cfg.bad_pose_consecutive_steps
    _, penalty = termination_mdp.compute_pose_termination(
        imu_z=physics["imu_z"],
        upright=physics["upright"],
        lean_fwd_body=physics["lean_fwd_body"],
        both_feet_on_floor=biped.both_feet_on_floor,
        min_imu_z=term_cfg.min_imu_z,
        min_imu_upright=term_cfg.min_imu_upright,
        max_backward_lean_body=term_cfg.max_backward_lean_body,
        max_forward_lean_both_feet=term_cfg.max_forward_lean_both_feet,
        pose_termination_penalty=term_cfg.pose_termination_penalty,
    )
    return torch.where(pose_done, penalty, torch.zeros_like(penalty))
