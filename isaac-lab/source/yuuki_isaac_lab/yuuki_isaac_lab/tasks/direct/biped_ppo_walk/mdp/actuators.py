# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""12 関節名・ctrlrange（exp_030 lib/actuators.py + main.xml 由来）。"""

from __future__ import annotations

import torch

# 関節名（MuJoCo main.xml と順序一致）
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

# 立位 keyframe の中立角 [rad]（全軸 0）
STAND_NEUTRAL_POS: tuple[float, ...] = (0.0,) * ACTION_DIM

# MuJoCo actuator ctrlrange [lo, hi]（rad）
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

# ボディ・サイト参照名
ROOT_BODY_NAME = "basket_thigh"
LEFT_SOLE_BODY = "left_sole"
RIGHT_SOLE_BODY = "right_sole"
LEFT_FOOT_GEOM = "foot_plate"
RIGHT_FOOT_GEOM = "right_foot_plate"

# sole ボディ座標系での site オフセット [m]（main.xml）
FOOT_SITE_OFFSET = (0.10, 0.0, 0.001)
HEEL_SITE_OFFSET = (-0.025, 0.0, 0.0)
TOE_SITE_OFFSET = (0.205, 0.0, 0.0)
IMU_OFFSET = (0.0, 0.0, 0.05)

# 接地判定 [m]: min Z <= ON で接地候補、max Z >= OFF で離地確定（PhysX 誤検出抑制）
FOOT_CONTACT_Z_ON = 0.018
FOOT_CONTACT_Z_OFF = 0.045
# 後方互換（env_cfg.termination が参照）
FOOT_CONTACT_Z_THRESH = FOOT_CONTACT_Z_ON


def ctrl_ranges_tensor(device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    """ctrlrange の下限・上限テンソル [action_dim]。"""
    lo = torch.tensor([r[0] for r in CTRL_RANGES], device=device, dtype=torch.float32)
    hi = torch.tensor([r[1] for r in CTRL_RANGES], device=device, dtype=torch.float32)
    return lo, hi


def neutral_pos_tensor(device: torch.device) -> torch.Tensor:
    """立位中立角テンソル [action_dim]。"""
    return torch.tensor(STAND_NEUTRAL_POS, device=device, dtype=torch.float32)
