# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""exp_030 両脚モデルを Isaac Lab から spawn する ArticulationCfg。"""

from __future__ import annotations

import os

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg

# Isaac Lab 用 MJCF（床 geom なし・ルート高さは init_state で指定）
_MJCF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_isaac.xml")

# exp_030 stand keyframe: 全 12 関節 0 rad、ルート高さ 0.66 m
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

# MuJoCo position actuator の kp/kv（main.xml と一致）
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
    # MJCF インポート後は worldBody と basket_thigh の 2 articulation ができる。
    # ロボット本体（freejoint ルート）を明示する。
    articulation_root_prim_path="/basket_thigh/basket_thigh",
    spawn=sim_utils.MjcfFileCfg(
        asset_path=_MJCF_PATH,
        fix_base=False,
        import_sites=True,
        activate_contact_sensors=True,
        # MJCF→USD キャッシュを利用（main_isaac.xml 更新時のみ True にする）
        force_usd_conversion=False,
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
