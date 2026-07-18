# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# pyright: reportMissingImports=false

"""BipedPpoWalk environment config (ManagerBasedRLEnv)."""

from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.assets import AssetBaseCfg
from isaaclab.envs import ManagerBasedRLEnvCfg, ViewerCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import PhysxCfg, SimulationCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils import configclass

from yuuki_isaac_lab.assets.robots.yuuki_biped import YUUKI_BIPED_CFG

from .mdp.actuators import FOOT_CONTACT_Z_OFF, FOOT_CONTACT_Z_ON, JOINT_NAMES
from .mdp.observation_params import BipedObservationParams
from .mdp.walk_params import BipedWalkParams

import yuuki_isaac_lab.tasks.manager_based.biped_ppo_walk.mdp as mdp

_ROBOT_JOINTS = SceneEntityCfg("robot", joint_names=list(JOINT_NAMES))


@configclass
class BipedTerminationParams:
    """Termination thresholds."""

    # かご付近（basket_thigh 上 IMU）の最低高さ [m]。
    min_imu_z: float = 0.18
    # 体幹の傾き閾値（IMU 上方向の Z 成分。小さいほど傾いている）。
    min_imu_upright: float = 0.35
    pose_termination_penalty: float = -10.0
    foot_contact_z_on: float = FOOT_CONTACT_Z_ON
    foot_contact_z_off: float = FOOT_CONTACT_Z_OFF


@configclass
class BipedPpoWalkSceneCfg(InteractiveSceneCfg):
    """Biped robot on a flat ground plane."""

    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="plane",
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.15,
            dynamic_friction=1.15,
            restitution=0.0,
        ),
        debug_vis=False,
    )
    robot = YUUKI_BIPED_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")
    light = AssetBaseCfg(
        prim_path="/World/light",
        spawn=sim_utils.DomeLightCfg(intensity=2000.0, color=(0.75, 0.75, 0.75)),
    )


@configclass
class ActionsCfg:
    """12-DOF joint position targets (neutral-offset mapping)."""

    joint_pos = mdp.BipedNeutralJointPositionActionCfg(
        asset_name="robot",
        joint_names=list(JOINT_NAMES),
    )


@configclass
class ObservationsCfg:
    """54-dim policy observation (order preserved by ObservationManager)."""

    @configclass
    class PolicyCfg(ObsGroup):
        """Observations for the PPO policy."""

        imu_dx = ObsTerm(func=mdp.imu_dx)
        imu_zaxis = ObsTerm(func=mdp.imu_zaxis)
        single_support = ObsTerm(func=mdp.single_support_flag)

        # imu_gyro = ObsTerm(func=mdp.imu_gyro)
        # imu_height = ObsTerm(func=mdp.imu_height)
        # left_foot_contact = ObsTerm(func=mdp.left_foot_contact)
        # right_foot_contact = ObsTerm(func=mdp.right_foot_contact)
        # left_foot_dx = ObsTerm(func=mdp.left_foot_dx)
        # right_foot_dx = ObsTerm(func=mdp.right_foot_dx)
        # left_foot_height = ObsTerm(func=mdp.left_foot_height)
        # right_foot_height = ObsTerm(func=mdp.right_foot_height)
        # joint_pos = ObsTerm(func=mdp.joint_pos_normalized, params={"asset_cfg": _ROBOT_JOINTS})
        # joint_vel = ObsTerm(func=mdp.joint_vel_normalized, params={"asset_cfg": _ROBOT_JOINTS})
        # actions = ObsTerm(func=mdp.last_action)
        # support_side = ObsTerm(func=mdp.support_side)
        # same_side_streak = ObsTerm(func=mdp.same_side_streak_normalized)
        # episode_progress = ObsTerm(func=mdp.episode_progress)

        def __post_init__(self) -> None:
            self.enable_corruption = False
            self.concatenate_terms = True

    policy: PolicyCfg = PolicyCfg()


@configclass
class EventsCfg:
    """Reset events (default stand pose + optional joint noise)."""

    reset_robot = EventTerm(
        func=mdp.reset_robot_to_default,
        mode="reset",
        params={"asset_name": "robot"},
    )
    reset_joint_noise = EventTerm(
        func=mdp.apply_reset_joint_noise,
        mode="reset",
        params={"asset_name": "robot", "noise_rad": 0.010},
    )


@configclass
class RewardsCfg:
    """Reward terms for +X alternating biped walk."""

    forward_imu = RewTerm(func=mdp.forward_imu, weight=70.0)
    # forward_velocity = RewTerm(func=mdp.forward_velocity, weight=8.0)
    # forward_foot = RewTerm(func=mdp.forward_foot, weight=70.0)
    # progress = RewTerm(func=mdp.progress, weight=50.0)

    # upright_bonus = RewTerm(func=mdp.upright_bonus, weight=0.8)
    # push_off_bonus = RewTerm(func=mdp.push_off_bonus, weight=0.35)
    # landing_bonus = RewTerm(func=mdp.landing_bonus, weight=0.35)
    # alternating_landing_bonus = RewTerm(func=mdp.alternating_landing_bonus, weight=2.0)
    # left_landing_bonus = RewTerm(func=mdp.left_landing_bonus, weight=1.8)
    # left_single_support_bonus = RewTerm(func=mdp.left_single_support_bonus, weight=1.5)
    # foot_swap_bonus = RewTerm(func=mdp.foot_swap_bonus, weight=1.2)
    # swing_clearance_bonus = RewTerm(func=mdp.swing_clearance_bonus, weight=0.3)
    # duration_bonus = RewTerm(func=mdp.duration_bonus, weight=0.5)
    # displacement_milestone_bonus = RewTerm(func=mdp.displacement_milestone_bonus, weight=1.0)
    # survival_milestone_bonus = RewTerm(func=mdp.survival_milestone_bonus, weight=1.0)
    # alive_bonus = RewTerm(func=mdp.alive_bonus, weight=0.9)
    # displacement_progress_bonus = RewTerm(func=mdp.displacement_progress_bonus, weight=0.4)
    # long_horizon_bonus = RewTerm(func=mdp.long_horizon_bonus, weight=1.4)

    # backward_lean_penalty = RewTerm(func=mdp.backward_lean_penalty, weight=-3.0)
    # forward_lean_penalty = RewTerm(func=mdp.forward_lean_penalty, weight=-4.0)
    # double_support_forward_lean_penalty = RewTerm(func=mdp.double_support_forward_lean_penalty, weight=-12.0)
    # fall_forward_penalty = RewTerm(func=mdp.fall_forward_penalty, weight=-18.0)
    # same_side_streak_penalty = RewTerm(func=mdp.same_side_streak_penalty, weight=-0.4)
    # contact_imbalance_penalty = RewTerm(func=mdp.contact_imbalance_penalty, weight=-0.35)
    # right_pivot_penalty = RewTerm(func=mdp.right_pivot_penalty, weight=-0.75)
    # backward_dx_penalty = RewTerm(func=mdp.backward_dx_penalty, weight=-12.0)
    # lateral_velocity_penalty = RewTerm(func=mdp.lateral_velocity_penalty, weight=-0.25)
    # angular_velocity_penalty = RewTerm(func=mdp.angular_velocity_penalty, weight=-0.04)
    # action_rate_penalty = RewTerm(func=mdp.action_rate_penalty, weight=-0.15)
    # imu_height_penalty = RewTerm(func=mdp.imu_height_penalty, weight=-2.0)
    # flight_duration_penalty = RewTerm(func=mdp.flight_duration_penalty, weight=-0.18)
    # knee_hyperflex_penalty = RewTerm(func=mdp.knee_hyperflex_penalty, weight=-2.5)
    # heading_misalign_penalty = RewTerm(func=mdp.heading_misalign_penalty, weight=-1.5)
    # lateral_tilt_penalty = RewTerm(func=mdp.lateral_tilt_penalty, weight=-2.5)
    # double_support_penalty = RewTerm(func=mdp.double_support_penalty, weight=-15.0)
    # effort_penalty = RewTerm(func=mdp.effort_penalty, weight=-2.0)
    # pose_termination_penalty = RewTerm(func=mdp.pose_termination_penalty, weight=1.0)


@configclass
class TerminationsCfg:
    """Episode termination terms."""

    bad_pose = DoneTerm(
        func=mdp.bad_pose,
        params={"min_imu_z": 0.18, "min_imu_upright": 0.35},
    )
    time_out = DoneTerm(func=mdp.time_out, time_out=True)


@configclass
class BipedPpoWalkEnvCfg(ManagerBasedRLEnvCfg):
    """12-DOF biped walk (+X) on ManagerBasedRLEnv."""

    decimation = 10
    episode_length_s = 30.0

    scene: BipedPpoWalkSceneCfg = BipedPpoWalkSceneCfg(
        num_envs=4096,
        env_spacing=3.0,
        replicate_physics=True,
        clone_in_fabric=True,
    )

    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    events: EventsCfg = EventsCfg()
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()

    walk_params: BipedWalkParams = BipedWalkParams()
    observation_params: BipedObservationParams = BipedObservationParams()
    termination_params: BipedTerminationParams = BipedTerminationParams()

    # IMU サイト位置に 3 軸フレーム（X=赤 / Y=緑 / Z=青）を毎ステップ描画するか。
    # GUI 起動時のみ有効（headless では自動的に無効化）。学習時は負荷回避のため False を推奨。
    debug_vis_imu_frame: bool = False

    def __post_init__(self) -> None:
        self.sim = SimulationCfg(
            dt=0.002,
            render_interval=self.decimation,
            physics_material=sim_utils.RigidBodyMaterialCfg(
                friction_combine_mode="multiply",
                restitution_combine_mode="multiply",
                static_friction=1.15,
                dynamic_friction=1.15,
                restitution=0.0,
            ),
            physx=PhysxCfg(
                enable_external_forces_every_iteration=True,
                solve_articulation_contact_last=True,
                min_velocity_iteration_count=1,
                gpu_max_rigid_contact_count=2**23,
                gpu_max_rigid_patch_count=2**22,
            ),
        )
        # Keep event / termination params aligned with nested configs.
        self.events.reset_joint_noise.params["noise_rad"] = 0.010
        self.terminations.bad_pose.params["min_imu_z"] = self.termination_params.min_imu_z
        self.terminations.bad_pose.params["min_imu_upright"] = self.termination_params.min_imu_upright


@configclass
class BipedPpoWalkEnvCfg_PLAY(BipedPpoWalkEnvCfg):
    """Play / visualization config (fewer envs, no fabric replicate)."""

    scene: BipedPpoWalkSceneCfg = BipedPpoWalkSceneCfg(
        num_envs=16,
        env_spacing=4.0,
        replicate_physics=False,
        clone_in_fabric=False,
    )

    # Play 時は IMU の姿勢を目視確認したいので 3 軸フレームを表示する。
    debug_vis_imu_frame: bool = True

    viewer: ViewerCfg = ViewerCfg(
        eye=(14.0, -18.0, 9.0),
        lookat=(0.0, 0.0, 0.55),
        resolution=(1280, 720),
    )
