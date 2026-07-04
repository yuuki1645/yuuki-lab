# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Policy action clipping and neutral-offset joint target mapping."""

from __future__ import annotations

import torch


def clip_policy_action(actions: torch.Tensor) -> torch.Tensor:
    """Clip policy outputs to [-1, 1]."""
    return torch.clamp(actions, -1.0, 1.0)


def actions_to_joint_targets(
    actions: torch.Tensor,
    ctrl_lo: torch.Tensor,
    ctrl_hi: torch.Tensor,
    neutral: torch.Tensor,
) -> torch.Tensor:
    """Map [-1, 1] actions to joint position targets [rad].

    action=0 corresponds to the stand neutral pose. Supports asymmetric ctrl ranges.
    """
    clipped = clip_policy_action(actions)
    pos_span = ctrl_hi - neutral
    neg_span = neutral - ctrl_lo
    pos_targets = neutral.unsqueeze(0) + clipped * pos_span.unsqueeze(0)
    neg_targets = neutral.unsqueeze(0) + clipped * neg_span.unsqueeze(0)
    return torch.where(clipped >= 0.0, pos_targets, neg_targets)
