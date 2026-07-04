# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""BipedPpoWalk environment config (ManagerBasedRLEnv)."""

from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.assets import AssetBaseCfg
from isaaclab.envs import ManagerBasedRLEnvCfg, ViewerCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import PhysxCfg, SimulationCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils import configclass

from yuuki_isaac_lab.assets.robots.yuuki_biped import YUUKI_BIPED_CFG
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.biped_ppo_walk_env_cfg import (
    BipedRewardCfg,
    BipedTerminationCfg,
)
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp.actuators import JOINT_NAMES

import yuuki_isaac_lab.tasks.manager_based.biped_ppo_walk.mdp as mdp


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
    """12-DOF joint position targets (exp_030 neutral-offset mapping)."""

    joint_pos = mdp.BipedNeutralJointPositionActionCfg(
        asset_name="robot",
        joint_names=list(JOINT_NAMES),
    )


@configclass
class ObservationsCfg:
    """54-dim policy observation (same layout as Direct task)."""

    @configclass
    class PolicyCfg(ObsGroup):
        obs = ObsTerm(func=mdp.policy_obs)

        def __post_init__(self) -> None:
            self.enable_corruption = False
            self.concatenate_terms = True

    policy: PolicyCfg = PolicyCfg()


@configclass
class EventsCfg:
    """Reset robot to stand keyframe with optional joint noise."""

    reset_robot = EventTerm(
        func=mdp.reset_robot_with_joint_noise,
        mode="reset",
        params={"asset_name": "robot", "noise_rad": 0.010},
    )


@configclass
class RewardsCfg:
    """Single reward term wrapping Direct compute_step_reward."""

    step = RewTerm(func=mdp.step_reward, weight=1.0)


@configclass
class TerminationsCfg:
    """Pose hysteresis termination and episode timeout."""

    bad_pose = DoneTerm(func=mdp.bad_pose)
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

    reward: BipedRewardCfg = BipedRewardCfg()
    termination: BipedTerminationCfg = BipedTerminationCfg()
    reset_joint_noise_rad: float = 0.010

    max_dx_per_step_base: float = 0.05
    max_foot_dx_per_step_base: float = 0.04
    max_gyro_rad_s: float = 10.0
    max_joint_vel_rad_s: float = 10.0
    max_imu_z: float = 1.2
    min_imu_z_norm: float = 0.0
    min_foot_z_norm: float = 0.0
    max_foot_z_norm: float = 0.35

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


@configclass
class BipedPpoWalkEnvCfg_PLAY(BipedPpoWalkEnvCfg):
    """Play / visualization config (fewer envs, no fabric replicate)."""

    scene: BipedPpoWalkSceneCfg = BipedPpoWalkSceneCfg(
        num_envs=16,
        env_spacing=4.0,
        replicate_physics=False,
        clone_in_fabric=False,
    )

    viewer: ViewerCfg = ViewerCfg(
        eye=(14.0, -18.0, 9.0),
        lookat=(0.0, 0.0, 0.55),
        resolution=(1280, 720),
    )
