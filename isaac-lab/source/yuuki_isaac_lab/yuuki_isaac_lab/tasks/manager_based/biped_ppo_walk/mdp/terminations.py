# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Termination terms for the biped walk task."""

from __future__ import annotations

import torch
from isaaclab.envs import ManagerBasedRLEnv

from . import termination as termination_mdp
from .episode_state import ensure_step_updated


def bad_pose(env: ManagerBasedRLEnv, min_imu_z: float, min_imu_upright: float) -> torch.Tensor:
    """Terminate when basket height is too low or body tilt exceeds threshold.

    ``imu_z`` is the world-frame height of the IMU on ``basket_thigh`` (かご付近).
    ``upright`` is the Z component of the IMU up axis (1.0 = upright, smaller = more tilted).
    """
    snap = ensure_step_updated(env)
    physics = snap.physics

    low_height = physics["imu_z"] < min_imu_z
    too_tilted = physics["upright"] < min_imu_upright

    return low_height | too_tilted


def time_out(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Truncate episode at max length."""
    return env.episode_length_buf >= env.max_episode_length - 1
