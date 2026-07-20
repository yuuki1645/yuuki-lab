# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Yuuki biped ArticulationCfg (USD asset).

Authoring 正本は ``urdf/yuuki_biped.urdf``。実行時は prebuilt USD を読む。
URDF を編集したら README の手動手順で USD を再生成すること。
"""

from __future__ import annotations

import os

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg

# Prebuilt USD (instanceable). Author from urdf/, convert with Isaac Lab convert_urdf.py.
_USD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usd", "yuuki_biped.usd")

# Stand pose: all 12 joints 0 rad, root height 0.66 m
_STAND_JOINT_POS = {
    "left_hip_roll": 0.0,
    "left_hip_pitch": 0.0,
    "left_knee_pitch": 0.0,
    "left_ankle_pitch": 0.0,
    "left_ankle_roll": 0.0,
    "right_hip_roll": 0.0,
    "right_hip_pitch": 0.0,
    "right_knee_pitch": 0.0,
    "right_ankle_pitch": 0.0,
    "right_ankle_roll": 0.0,
    "basket_top_roll": 0.0,
    "balance_pitch": 0.0,
}

# Joint PD gains (legacy MuJoCo position-actuator kp/kv values)
_LEG_STIFFNESS = 85.0
_LEG_DAMPING = 12.0
_KNEE_STIFFNESS = 120.0
_KNEE_DAMPING = 14.0
_ANKLE_PITCH_STIFFNESS = 70.0
_ANKLE_PITCH_DAMPING = 10.0
_ANKLE_ROLL_STIFFNESS = 50.0
_ANKLE_ROLL_DAMPING = 8.0
_TORSO_STIFFNESS = 85.0
_TORSO_DAMPING = 12.0

YUUKI_BIPED_CFG = ArticulationCfg(
    # USD has both worldBody and basket_thigh articulations; pick the free-joint robot root.
    # Path is relative to the spawned prim (e.g. .../Robot). When the USD defaultPrim is
    # ``main_isaac``, that namespace is stripped and bodies appear directly under Robot.
    articulation_root_prim_path="/basket_thigh/basket_thigh",
    spawn=sim_utils.UsdFileCfg(
        usd_path=_USD_PATH,
        activate_contact_sensors=True,
        rigid_props=sim_utils.RigidBodyPropertiesCfg(
            disable_gravity=False,
            max_depenetration_velocity=1.0,
        ),
        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            enabled_self_collisions=True,
            solver_position_iteration_count=8,
            solver_velocity_iteration_count=4,
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.66),
        rot=(1.0, 0.0, 0.0, 0.0),
        joint_pos=_STAND_JOINT_POS,
        joint_vel={".*": 0.0},
    ),
    actuators={
        "left_leg": ImplicitActuatorCfg(
            joint_names_expr=[
                "left_hip_roll",
                "left_hip_pitch",
                "left_knee_pitch",
                "left_ankle_pitch",
                "left_ankle_roll",
            ],
            stiffness={
                "left_hip_roll": _LEG_STIFFNESS,
                "left_hip_pitch": _LEG_STIFFNESS,
                "left_knee_pitch": _KNEE_STIFFNESS,
                "left_ankle_pitch": _ANKLE_PITCH_STIFFNESS,
                "left_ankle_roll": _ANKLE_ROLL_STIFFNESS,
            },
            damping={
                "left_hip_roll": _LEG_DAMPING,
                "left_hip_pitch": _LEG_DAMPING,
                "left_knee_pitch": _KNEE_DAMPING,
                "left_ankle_pitch": _ANKLE_PITCH_DAMPING,
                "left_ankle_roll": _ANKLE_ROLL_DAMPING,
            },
        ),
        "right_leg": ImplicitActuatorCfg(
            joint_names_expr=[
                "right_hip_roll",
                "right_hip_pitch",
                "right_knee_pitch",
                "right_ankle_pitch",
                "right_ankle_roll",
            ],
            stiffness={
                "right_hip_roll": _LEG_STIFFNESS,
                "right_hip_pitch": _LEG_STIFFNESS,
                "right_knee_pitch": _KNEE_STIFFNESS,
                "right_ankle_pitch": _ANKLE_PITCH_STIFFNESS,
                "right_ankle_roll": _ANKLE_ROLL_STIFFNESS,
            },
            damping={
                "right_hip_roll": _LEG_DAMPING,
                "right_hip_pitch": _LEG_DAMPING,
                "right_knee_pitch": _KNEE_DAMPING,
                "right_ankle_pitch": _ANKLE_PITCH_DAMPING,
                "right_ankle_roll": _ANKLE_ROLL_DAMPING,
            },
        ),
        "torso": ImplicitActuatorCfg(
            joint_names_expr=["basket_top_roll", "balance_pitch"],
            stiffness=_TORSO_STIFFNESS,
            damping=_TORSO_DAMPING,
        ),
    },
    soft_joint_pos_limit_factor=0.95,
)
