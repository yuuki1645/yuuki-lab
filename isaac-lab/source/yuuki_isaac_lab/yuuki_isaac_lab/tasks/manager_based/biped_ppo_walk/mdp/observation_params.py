# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Observation normalization parameters."""

from __future__ import annotations

from isaaclab.utils import configclass


@configclass
class BipedObservationParams:
    """Scales for policy observation terms (54-dim when concatenated)."""

    max_dx_per_step_base: float = 0.05
    max_foot_dx_per_step_base: float = 0.04
    max_gyro_rad_s: float = 10.0
    max_joint_vel_rad_s: float = 10.0
    max_imu_z: float = 1.2
    min_imu_z_norm: float = 0.0
    min_foot_z_norm: float = 0.0
    max_foot_z_norm: float = 0.35
    same_side_streak_norm_steps: float = 40.0
