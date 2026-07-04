# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Shared reward helpers (milestone tracking, effort, forward gating)."""

from __future__ import annotations

import torch

from .gait import BipedStepContext


def compute_milestone_bonus(
    progress: torch.Tensor,
    milestone_level: torch.Tensor,
    targets: tuple[float, ...],
    scales: tuple[float, ...],
) -> tuple[torch.Tensor, torch.Tensor]:
    """One-shot milestone bonus when progress crosses each target."""
    bonus = torch.zeros_like(progress)
    new_level = milestone_level.clone()
    for idx, (target, scale) in enumerate(zip(targets, scales, strict=True)):
        newly_reached = (progress >= target) & (new_level <= idx)
        bonus = bonus + torch.where(newly_reached, torch.full_like(bonus, scale), torch.zeros_like(bonus))
        new_level = torch.where(newly_reached, torch.full_like(new_level, idx + 1), new_level)
    return bonus, new_level


def compute_effort_penalty(
    applied_torque: torch.Tensor,
    joint_vel: torch.Tensor,
    dt: float,
    scale: float,
) -> torch.Tensor:
    """Power proxy penalty: sum(|tau * qdot|) * dt * scale."""
    power = torch.sum(torch.abs(applied_torque * joint_vel), dim=-1) * dt
    return power * scale


def compute_forward_allowed(
    reward_cfg,
    biped: BipedStepContext,
    *,
    upright: torch.Tensor,
    lean_fwd_body: torch.Tensor,
) -> torch.Tensor:
    """Gate mask for primary forward rewards."""
    allowed = upright >= reward_cfg.forward_min_upright
    if reward_cfg.forward_require_foot_contact:
        allowed = allowed & biped.any_foot_on_floor
    if reward_cfg.forward_require_single_support:
        allowed = allowed & biped.single_support
    if reward_cfg.forward_block_lean_both_feet is not None:
        fall_block = biped.both_feet_on_floor & (lean_fwd_body > reward_cfg.forward_block_lean_both_feet)
        allowed = allowed & (~fall_block)
    if reward_cfg.forward_block_same_side_streak > 0:
        allowed = allowed & (biped.same_side_streak <= reward_cfg.forward_block_same_side_streak)
    if reward_cfg.forward_block_right_pivot_streak > 0:
        right_pivot_block = biped.single_support & (biped.single_support_side == -1)
        right_pivot_block = right_pivot_block & (biped.same_side_streak > float(reward_cfg.forward_block_right_pivot_streak))
        allowed = allowed & (~right_pivot_block)
    return allowed


def compute_shaping_allowed(reward_cfg, forward_allowed: torch.Tensor, dx: torch.Tensor) -> torch.Tensor:
    """Gate mask for gait-shaping bonuses."""
    allowed = forward_allowed
    if reward_cfg.shaping_require_forward_motion:
        allowed = allowed & (dx >= reward_cfg.shaping_min_dx)
    return allowed
