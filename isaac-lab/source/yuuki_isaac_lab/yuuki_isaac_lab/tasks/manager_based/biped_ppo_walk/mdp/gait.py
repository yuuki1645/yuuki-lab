# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Biped gait phase state (landing edges, single support, alternating steps)."""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class BipedStepContext:
    """Per-step biped gait context (batched tensors)."""

    left_landed: torch.Tensor
    right_landed: torch.Tensor
    aerial_steps: torch.Tensor
    both_feet_on_floor: torch.Tensor
    any_foot_on_floor: torch.Tensor
    single_support: torch.Tensor
    single_support_side: torch.Tensor
    alternating_landing: torch.Tensor
    same_side_streak: torch.Tensor
    foot_swap: torch.Tensor


def advance_biped_context(
    *,
    left_on_floor: torch.Tensor,
    right_on_floor: torch.Tensor,
    prev_left_on_floor: torch.Tensor,
    prev_right_on_floor: torch.Tensor,
    prev_single_support_side: torch.Tensor,
    aerial_steps: torch.Tensor,
    same_side_streak: torch.Tensor,
    imu_z: torch.Tensor,
    prev_imu_z: torch.Tensor,
) -> tuple[BipedStepContext, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Update landing edges, alternating gait flags, and aerial step counter."""
    del imu_z, prev_imu_z  # reserved for future height-gated gait logic

    left_landed = left_on_floor & (~prev_left_on_floor)
    right_landed = right_on_floor & (~prev_right_on_floor)
    any_foot = left_on_floor | right_on_floor
    both_feet = left_on_floor & right_on_floor
    single_support = (left_on_floor & (~right_on_floor)) | (right_on_floor & (~left_on_floor))

    support_side = torch.zeros_like(prev_single_support_side)
    support_side = torch.where(left_on_floor & (~right_on_floor), torch.ones_like(support_side), support_side)
    support_side = torch.where(right_on_floor & (~left_on_floor), -torch.ones_like(support_side), support_side)

    alternating_landing = (left_landed & (prev_single_support_side == -1)) | (
        right_landed & (prev_single_support_side == 1)
    )

    foot_swap = (
        single_support
        & (support_side != 0)
        & (prev_single_support_side != 0)
        & (support_side != prev_single_support_side)
    )

    side_unchanged = single_support & (support_side != 0) & (support_side == prev_single_support_side)
    new_same_side_streak = torch.where(
        side_unchanged,
        same_side_streak + 1,
        torch.where(single_support, torch.ones_like(same_side_streak), torch.zeros_like(same_side_streak)),
    )

    aerial_steps = torch.where(any_foot, torch.zeros_like(aerial_steps), aerial_steps + 1)

    new_prev_left = left_on_floor
    new_prev_right = right_on_floor
    new_prev_side = torch.where(single_support, support_side, prev_single_support_side)

    ctx = BipedStepContext(
        left_landed=left_landed,
        right_landed=right_landed,
        aerial_steps=aerial_steps,
        both_feet_on_floor=both_feet,
        any_foot_on_floor=any_foot,
        single_support=single_support,
        single_support_side=support_side,
        alternating_landing=alternating_landing,
        same_side_streak=new_same_side_streak,
        foot_swap=foot_swap,
    )
    return ctx, new_prev_left, new_prev_right, new_prev_side, aerial_steps, new_same_side_streak


def advance_progress(
    imu_x: torch.Tensor,
    best_imu_x: torch.Tensor,
    *,
    upright: torch.Tensor,
    single_support: torch.Tensor,
    progress_min_upright: float,
    progress_require_single_support: bool,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Episode IMU +X progress since last best [m]."""
    allowed = upright >= progress_min_upright
    if progress_require_single_support:
        allowed = allowed & single_support
    progress = torch.clamp(imu_x - best_imu_x, min=0.0)
    progress = torch.where(allowed, progress, torch.zeros_like(progress))
    new_best = torch.maximum(best_imu_x, imu_x)
    return progress, new_best
