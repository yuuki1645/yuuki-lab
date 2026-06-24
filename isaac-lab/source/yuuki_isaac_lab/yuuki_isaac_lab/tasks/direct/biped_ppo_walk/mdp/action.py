# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""ポリシー [-1, 1] → 関節位置目標（exp_030 lib/ctrl.py 由来・バッチ対応）。"""

from __future__ import annotations

import torch

from .actuators import CTRL_RANGES


def clip_policy_action(actions: torch.Tensor) -> torch.Tensor:
    """ポリシー出力を [-1, 1] にクリップする。"""
    return torch.clamp(actions, -1.0, 1.0)


def actions_to_joint_targets(
    actions: torch.Tensor,
    ctrl_lo: torch.Tensor,
    ctrl_hi: torch.Tensor,
    neutral: torch.Tensor,
) -> torch.Tensor:
    """[-1, 1] の action を関節位置目標 [rad] に写像する。

    action=0 は neutral（stand 姿勢）。非対称 ctrlrange にも対応。
    actions: [num_envs, action_dim]
  ctrl_lo/hi/neutral: [action_dim]
    """
    clipped = clip_policy_action(actions)
    # 正側: neutral + a * (hi - neutral)
    pos_span = ctrl_hi - neutral
    neg_span = neutral - ctrl_lo
    pos_targets = neutral.unsqueeze(0) + clipped * pos_span.unsqueeze(0)
    neg_targets = neutral.unsqueeze(0) + clipped * neg_span.unsqueeze(0)
    return torch.where(clipped >= 0.0, pos_targets, neg_targets)
