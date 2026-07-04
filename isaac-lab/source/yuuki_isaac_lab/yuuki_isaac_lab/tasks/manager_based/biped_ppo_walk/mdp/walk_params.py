# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Gait / reward logic parameters (weights live on ``RewardsCfg`` RewTerms)."""

from __future__ import annotations

from isaaclab.utils import configclass


@configclass
class BipedWalkParams:
    """Thresholds and milestone tables for biped walk MDP logic."""

    shaping_require_forward_motion: bool = True
    shaping_min_dx: float = 0.00005

    forward_min_upright: float = 0.50
    forward_min_dx: float = 0.0005
    forward_require_foot_contact: bool = True
    forward_require_single_support: bool = True
    forward_block_lean_both_feet: float = 0.07
    forward_vel_max: float = 0.4
    forward_block_same_side_streak: int = 12
    forward_block_right_pivot_streak: int = 0
    forward_foot_left_stance_only: bool = False

    fall_forward_lean_thresh: float = 0.06
    ds_forward_lean_thresh: float = 0.05
    double_support_min_forward: float = 0.001

    push_off_min_foot_dx: float = 0.002
    push_off_min_imu_dz: float = 0.003
    push_off_min_knee_ext_vel: float = 0.12
    landing_max_toe_z: float = 0.07
    landing_max_heel_z: float = 0.07
    landing_max_forward_lean: float = 0.3

    same_side_streak_penalty_after: int = 6
    contact_imbalance_streak_after: int = 4
    right_pivot_streak_after: int = 2
    backward_dx_thresh: float = 0.0003
    left_single_support_min_dx: float = 0.0004
    swing_min_foot_z: float = 0.04

    upright_bonus_thresh: float = 0.6
    upright_bonus_min_dx: float = 0.0
    lean_backward_thresh: float = 0.12
    lean_forward_thresh: float = 0.14
    lean_forward_min_aerial_steps: int = 2
    heading_align_min: float = 0.85
    lateral_tilt_thresh: float = 0.12
    aerial_duration_penalty_after_steps: int = 4

    progress_min_upright: float = 0.6
    progress_require_single_support: bool = True

    displacement_milestone_targets: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 15.0)
    displacement_milestone_scales: tuple[float, ...] = (2.0, 6.0, 35.0, 40.0, 45.0)
    survival_milestone_targets: tuple[int, ...] = (80, 160, 320, 500, 800, 1200, 1600)
    survival_milestone_scales: tuple[float, ...] = (6.0, 12.0, 28.0, 50.0, 80.0, 120.0, 160.0)

    alive_min_upright: float = 0.64
    alive_min_imu_z: float = 0.48
    long_horizon_step_threshold: int = 50

    knee_hyperflex_max_rad: float = 0.95
    knee_hyperflex_aerial_only: bool = True
    target_imu_z: float = 0.55
    target_imu_z_single_stance: float = 0.5
    target_imu_z_double_stance: float = 0.52
    height_penalty_aerial_crash_z: float = 0.42
