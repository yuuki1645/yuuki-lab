# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Joint names, control ranges, and foot contact thresholds for the yuuki biped."""

from __future__ import annotations

import torch

# Joint order matches MJCF / Isaac articulation naming.
JOINT_NAMES: tuple[str, ...] = (
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee_pitch",
    "left_ankle_pitch",
    "left_ankle_roll",
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee_pitch",
    "right_ankle_pitch",
    "right_ankle_roll",
    "basket_top_roll",
    "balance_pitch",
)

ACTION_DIM = len(JOINT_NAMES)

# Stand keyframe neutral angles [rad] (all zeros).
STAND_NEUTRAL_POS: tuple[float, ...] = (0.0,) * ACTION_DIM

# MuJoCo actuator ctrlrange [lo, hi] mapped to joint position limits [rad].
CTRL_RANGES: tuple[tuple[float, float], ...] = (
    (-0.524, 1.571),
    (-1.919, 0.524),
    (0.0, 1.745),
    (-0.349, 1.571),
    (-0.349, 0.349),
    (-0.524, 1.571),
    (-1.919, 0.524),
    (0.0, 1.745),
    (-0.349, 1.571),
    (-0.349, 0.349),
    (-0.785, 0.785),
    (-0.785, 0.785),
)

ROOT_BODY_NAME = "basket_thigh"
LEFT_SOLE_BODY = "left_sole"
RIGHT_SOLE_BODY = "right_sole"
LEFT_FOOT_GEOM = "foot_plate"
RIGHT_FOOT_GEOM = "right_foot_plate"

FOOT_SITE_OFFSET = (0.10, 0.0, 0.001)
HEEL_SITE_OFFSET = (-0.025, 0.0, 0.0)
TOE_SITE_OFFSET = (0.205, 0.0, 0.0)
IMU_OFFSET = (0.0, 0.0, 0.05)

# Foot contact hysteresis [m] (PhysX height proxy).
FOOT_CONTACT_Z_ON = 0.018
FOOT_CONTACT_Z_OFF = 0.045
FOOT_CONTACT_Z_THRESH = FOOT_CONTACT_Z_ON


def ctrl_ranges_tensor(device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    """Return lower/upper joint limit tensors [action_dim]."""
    lo = torch.tensor([r[0] for r in CTRL_RANGES], device=device, dtype=torch.float32)
    hi = torch.tensor([r[1] for r in CTRL_RANGES], device=device, dtype=torch.float32)
    return lo, hi


def neutral_pos_tensor(device: torch.device) -> torch.Tensor:
    """Return stand neutral joint angles [action_dim]."""
    return torch.tensor(STAND_NEUTRAL_POS, device=device, dtype=torch.float32)
