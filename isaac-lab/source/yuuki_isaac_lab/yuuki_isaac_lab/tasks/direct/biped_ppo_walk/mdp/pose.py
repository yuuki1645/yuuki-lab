# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""ボディフレーム姿勢量（exp_030 lib/pose.py 由来・torch 版）。"""

from __future__ import annotations

import torch


def body_xaxis_world(quat_wxyz: torch.Tensor) -> torch.Tensor:
    """ルートクォータニオンからボディ +X 軸のワールド単位ベクトル [num_envs, 3]。"""
    w, x, y, z = quat_wxyz[:, 0], quat_wxyz[:, 1], quat_wxyz[:, 2], quat_wxyz[:, 3]
    # 回転行列の第 1 列（ローカル X 軸）
    xx = 1.0 - 2.0 * (y * y + z * z)
    xy = 2.0 * (x * y + w * z)
    xz = 2.0 * (x * z - w * y)
    return torch.stack([xx, xy, xz], dim=-1)


def imu_zaxis_world(quat_wxyz: torch.Tensor) -> torch.Tensor:
    """IMU サイト（ルートと同姿勢近似）の上向き軸 [num_envs, 3]。"""
    w, x, y, z = quat_wxyz[:, 0], quat_wxyz[:, 1], quat_wxyz[:, 2], quat_wxyz[:, 3]
    zx = 2.0 * (x * z + w * y)
    zy = 2.0 * (y * z - w * x)
    zz = 1.0 - 2.0 * (x * x + y * y)
    return torch.stack([zx, zy, zz], dim=-1)


def pose_metrics(
    imu_zaxis: torch.Tensor,
    body_x: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """(lean_fwd_body, heading_align, tilt_horiz) を返す。"""
    lean_fwd_body = torch.sum(imu_zaxis * body_x, dim=-1)
    heading_align = body_x[:, 0]
    tilt_horiz = torch.sqrt(imu_zaxis[:, 0] ** 2 + imu_zaxis[:, 1] ** 2)
    return lean_fwd_body, heading_align, tilt_horiz
