# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Pose and foot-contact helpers for termination and reward gating."""

from __future__ import annotations

import torch


def compute_pose_termination(
    *,
    imu_z: torch.Tensor,
    upright: torch.Tensor,
    lean_fwd_body: torch.Tensor,
    both_feet_on_floor: torch.Tensor | None = None,
    min_imu_z: float,
    min_imu_upright: float,
    max_backward_lean_body: float,
    max_forward_lean_both_feet: float | None = None,
    pose_termination_penalty: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Pose-based termination mask and terminal penalty [num_envs]."""
    low_z = imu_z < min_imu_z
    low_upright = upright < min_imu_upright
    backward_lean = lean_fwd_body < -max_backward_lean_body
    forward_fall = torch.zeros_like(low_z)
    if both_feet_on_floor is not None and max_forward_lean_both_feet is not None:
        forward_fall = both_feet_on_floor & (lean_fwd_body > max_forward_lean_both_feet)
    terminated = low_z | low_upright | backward_lean | forward_fall
    penalty = torch.where(terminated, torch.full_like(imu_z, pose_termination_penalty), torch.zeros_like(imu_z))
    return terminated, penalty


def foot_contact_from_heights(
    foot_z: torch.Tensor,
    toe_z: torch.Tensor,
    heel_z: torch.Tensor,
    on_thresh: float,
    off_thresh: float | None = None,
) -> torch.Tensor:
    """Foot contact from sole/toe/heel height with optional swing-off hysteresis."""
    min_z = torch.minimum(torch.minimum(foot_z, toe_z), heel_z)
    if off_thresh is None:
        return min_z <= on_thresh
    max_z = torch.maximum(torch.maximum(foot_z, toe_z), heel_z)
    clearly_off = max_z > off_thresh
    on = min_z <= on_thresh
    return on & (~clearly_off)
