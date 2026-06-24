# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""早期終了（exp_030 sim/termination.py 由来・torch 版）。"""

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
    """姿勢に基づく終了とペナルティ [num_envs]。"""
    low_z = imu_z < min_imu_z
    low_upright = upright < min_imu_upright
    backward_lean = lean_fwd_body < -max_backward_lean_body
    forward_fall = torch.zeros_like(low_z)
    if both_feet_on_floor is not None and max_forward_lean_both_feet is not None:
        # 両足支持のまま過度に前傾 → 足を出さない前転を早期終了
        forward_fall = both_feet_on_floor & (lean_fwd_body > max_forward_lean_both_feet)
    terminated = low_z | low_upright | backward_lean | forward_fall
    penalty = torch.where(terminated, torch.full_like(imu_z, pose_termination_penalty), torch.zeros_like(imu_z))
    return terminated, penalty


def foot_contact_proxy(foot_z: torch.Tensor, thresh: float) -> torch.Tensor:
    """足裏 site の世界 Z が閾値以下なら接地とみなす（ContactSensor 未使用時のフォールバック）。"""
    return foot_z <= thresh


def foot_contact_from_heights(
    foot_z: torch.Tensor,
    toe_z: torch.Tensor,
    heel_z: torch.Tensor,
    on_thresh: float,
    off_thresh: float | None = None,
) -> torch.Tensor:
    """踵・つま先・足裏の min/max Z で接地判定する（PhysX 向け）。

    min Z <= on_thresh で接地候補。max Z >= off_thresh ならスイング脚として非接地。
    """
    min_z = torch.minimum(torch.minimum(foot_z, toe_z), heel_z)
    if off_thresh is None:
        return min_z <= on_thresh
    max_z = torch.maximum(torch.maximum(foot_z, toe_z), heel_z)
    clearly_off = max_z > off_thresh
    on = min_z <= on_thresh
    return on & (~clearly_off)


def foot_contact_from_forces(net_forces: torch.Tensor, force_threshold: float) -> torch.Tensor:
    """ContactSensor の net force から足底接地を判定する [num_envs]。"""
    return torch.norm(net_forces, dim=-1) > force_threshold


def foot_contact_from_force_matrix(force_matrix: torch.Tensor, force_threshold: float) -> torch.Tensor:
    """床 filter 済み force matrix から足底接地を判定する [num_envs]。"""
    # force_matrix: [num_envs, num_filters, 3]
    max_filter_force = torch.max(torch.norm(force_matrix, dim=-1), dim=-1).values
    return max_filter_force > force_threshold
