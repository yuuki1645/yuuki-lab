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

from .mdp.actuators import FOOT_CONTACT_Z_OFF, FOOT_CONTACT_Z_ON, JOINT_NAMES
from .mdp.env_params import get_max_dx_per_step, get_max_foot_dx_per_step

import yuuki_isaac_lab.tasks.manager_based.biped_ppo_walk.mdp as mdp


@configclass
class BipedRewardCfg:
    """Reward coefficients (tuned for +X alternating single-support walk)."""

    enable_forward: bool = True
    enable_forward_vel: bool = True
    enable_forward_foot: bool = True
    enable_progress: bool = True
    enable_walk_shaping: bool = True
    shaping_require_forward_motion: bool = True
    shaping_min_dx: float = 0.00005
    enable_upright_bonus: bool = True
    enable_posture_penalties: bool = True
    enable_double_support: bool = True
    enable_flight_duration: bool = True
    enable_effort: bool = True
    enable_alive_bonus: bool = True
    alive_bonus_scale: float = 0.90
    alive_min_upright: float = 0.64
    alive_min_imu_z: float = 0.48
    enable_duration_bonus: bool = True
    duration_bonus_scale: float = 0.50
    enable_displacement_milestones: bool = True
    displacement_milestone_targets: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 15.0)
    displacement_milestone_scales: tuple[float, ...] = (2.0, 6.0, 35.0, 40.0, 45.0)
    enable_survival_milestones: bool = True
    survival_milestone_targets: tuple[int, ...] = (80, 160, 320, 500, 800, 1200, 1600)
    survival_milestone_scales: tuple[float, ...] = (6.0, 12.0, 28.0, 50.0, 80.0, 120.0, 160.0)

    forward_reward_scale: float = 70.0
    enable_displacement_progress_bonus: bool = True
    displacement_progress_scale: float = 0.40
    forward_vel_reward_scale: float = 8.0
    forward_vel_max: float = 0.4

    forward_min_upright: float = 0.50
    forward_min_dx: float = 0.0005
    forward_require_foot_contact: bool = True
    forward_require_single_support: bool = True
    forward_block_lean_both_feet: float = 0.07

    fall_forward_lean_thresh: float = 0.06
    fall_forward_penalty_scale: float = 18.0
    ds_forward_lean_thresh: float = 0.05
    ds_forward_lean_penalty_scale: float = 12.0
    double_support_penalty_scale: float = 15.0
    double_support_min_forward: float = 0.001
    push_off_bonus_scale: float = 0.35
    push_off_min_foot_dx: float = 0.002
    push_off_min_imu_dz: float = 0.003
    push_off_min_knee_ext_vel: float = 0.12
    landing_bonus_scale: float = 0.35
    landing_max_toe_z: float = 0.07
    landing_max_heel_z: float = 0.07
    landing_max_forward_lean: float = 0.3
    alternating_landing_bonus_scale: float = 2.00
    foot_swap_bonus_scale: float = 1.20
    left_landing_bonus_scale: float = 1.80
    same_side_streak_penalty_after: int = 6
    same_side_streak_penalty_scale: float = 0.40
    forward_block_same_side_streak: int = 12
    forward_block_right_pivot_streak: int = 0
    forward_foot_left_stance_only: bool = False
    contact_imbalance_penalty_scale: float = 0.35
    contact_imbalance_streak_after: int = 4
    right_pivot_penalty_scale: float = 0.75
    right_pivot_streak_after: int = 2
    backward_dx_penalty_scale: float = 12.0
    backward_dx_thresh: float = 0.0003
    left_single_support_bonus_scale: float = 1.50
    left_single_support_min_dx: float = 0.0004
    swing_clearance_bonus_scale: float = 0.30
    swing_min_foot_z: float = 0.04
    upright_bonus_scale: float = 0.8
    upright_bonus_thresh: float = 0.6
    upright_bonus_min_dx: float = 0.0
    lean_backward_penalty_scale: float = 3.0
    lean_backward_thresh: float = 0.12
    lean_forward_penalty_scale: float = 4.0
    lean_forward_thresh: float = 0.14
    lean_forward_min_aerial_steps: int = 2
    heading_align_min: float = 0.85
    heading_misalign_penalty_scale: float = 1.5
    lateral_tilt_thresh: float = 0.12
    lateral_tilt_penalty_scale: float = 2.5
    aerial_duration_penalty_scale: float = 0.18
    aerial_duration_penalty_after_steps: int = 4
    progress_reward_scale: float = 50.0
    progress_min_upright: float = 0.6
    progress_require_single_support: bool = True
    enable_long_horizon_bonus: bool = True
    long_horizon_step_threshold: int = 50
    long_horizon_bonus_scale: float = 1.40
    knee_hyperflex_max_rad: float = 0.95
    knee_hyperflex_penalty_scale: float = 2.5
    knee_hyperflex_aerial_only: bool = True
    imu_height_penalty_scale: float = 2.0
    target_imu_z: float = 0.55
    target_imu_z_single_stance: float = 0.5
    target_imu_z_double_stance: float = 0.52
    height_penalty_aerial_crash_z: float = 0.42
    effort_penalty_scale: float = 2.0
    action_rate_penalty_scale: float = 0.15
    lateral_vel_penalty_scale: float = 0.25
    ang_vel_penalty_scale: float = 0.04


@configclass
class BipedTerminationCfg:
    """Termination thresholds."""

    min_imu_z: float = 0.18
    min_imu_upright: float = 0.35
    max_backward_lean_body: float = 0.40
    max_forward_lean_both_feet: float = 0.22
    bad_pose_consecutive_steps: int = 65
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
    """54-dim policy observation."""

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
    """Per-term rewards; weights mirror ``BipedRewardCfg`` scales."""

    # Primary forward
    forward_imu = RewTerm(func=mdp.forward_imu, weight=70.0)
    forward_velocity = RewTerm(func=mdp.forward_velocity, weight=8.0)
    forward_foot = RewTerm(func=mdp.forward_foot, weight=70.0)
    progress = RewTerm(func=mdp.progress, weight=50.0)

    # Gait shaping bonuses
    upright_bonus = RewTerm(func=mdp.upright_bonus, weight=0.8)
    push_off_bonus = RewTerm(func=mdp.push_off_bonus, weight=0.35)
    landing_bonus = RewTerm(func=mdp.landing_bonus, weight=0.35)
    alternating_landing_bonus = RewTerm(func=mdp.alternating_landing_bonus, weight=2.0)
    left_landing_bonus = RewTerm(func=mdp.left_landing_bonus, weight=1.8)
    left_single_support_bonus = RewTerm(func=mdp.left_single_support_bonus, weight=1.5)
    foot_swap_bonus = RewTerm(func=mdp.foot_swap_bonus, weight=1.2)
    swing_clearance_bonus = RewTerm(func=mdp.swing_clearance_bonus, weight=0.3)
    duration_bonus = RewTerm(func=mdp.duration_bonus, weight=0.5)
    displacement_milestone_bonus = RewTerm(func=mdp.displacement_milestone_bonus, weight=1.0)
    survival_milestone_bonus = RewTerm(func=mdp.survival_milestone_bonus, weight=1.0)
    alive_bonus = RewTerm(func=mdp.alive_bonus, weight=0.9)
    displacement_progress_bonus = RewTerm(func=mdp.displacement_progress_bonus, weight=0.4)
    long_horizon_bonus = RewTerm(func=mdp.long_horizon_bonus, weight=1.4)

    # Posture / gait penalties (functions return positive magnitudes)
    backward_lean_penalty = RewTerm(func=mdp.backward_lean_penalty, weight=-3.0)
    forward_lean_penalty = RewTerm(func=mdp.forward_lean_penalty, weight=-4.0)
    double_support_forward_lean_penalty = RewTerm(func=mdp.double_support_forward_lean_penalty, weight=-12.0)
    fall_forward_penalty = RewTerm(func=mdp.fall_forward_penalty, weight=-18.0)
    same_side_streak_penalty = RewTerm(func=mdp.same_side_streak_penalty, weight=-0.4)
    contact_imbalance_penalty = RewTerm(func=mdp.contact_imbalance_penalty, weight=-0.35)
    right_pivot_penalty = RewTerm(func=mdp.right_pivot_penalty, weight=-0.75)
    backward_dx_penalty = RewTerm(func=mdp.backward_dx_penalty, weight=-12.0)
    lateral_velocity_penalty = RewTerm(func=mdp.lateral_velocity_penalty, weight=-0.25)
    angular_velocity_penalty = RewTerm(func=mdp.angular_velocity_penalty, weight=-0.04)
    action_rate_penalty = RewTerm(func=mdp.action_rate_penalty, weight=-0.15)
    imu_height_penalty = RewTerm(func=mdp.imu_height_penalty, weight=-2.0)
    flight_duration_penalty = RewTerm(func=mdp.flight_duration_penalty, weight=-0.18)
    knee_hyperflex_penalty = RewTerm(func=mdp.knee_hyperflex_penalty, weight=-2.5)
    heading_misalign_penalty = RewTerm(func=mdp.heading_misalign_penalty, weight=-1.5)
    lateral_tilt_penalty = RewTerm(func=mdp.lateral_tilt_penalty, weight=-2.5)
    double_support_penalty = RewTerm(func=mdp.double_support_penalty, weight=-15.0)
    effort_penalty = RewTerm(func=mdp.effort_penalty, weight=-1.0)
    pose_termination_penalty = RewTerm(func=mdp.pose_termination_penalty, weight=1.0)


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
        self._sync_reward_weights_from_cfg()

    def _sync_reward_weights_from_cfg(self) -> None:
        """Apply ``BipedRewardCfg`` scales and enable flags to ``RewardsCfg`` weights."""
        r = self.reward
        w = self.rewards

        w.forward_imu.weight = r.forward_reward_scale if r.enable_forward else 0.0
        w.forward_velocity.weight = r.forward_vel_reward_scale if r.enable_forward_vel else 0.0
        w.forward_foot.weight = r.forward_reward_scale if r.enable_forward_foot else 0.0
        w.progress.weight = r.progress_reward_scale if r.enable_progress else 0.0

        shaping = r.enable_walk_shaping
        w.upright_bonus.weight = r.upright_bonus_scale if (shaping and r.enable_upright_bonus) else 0.0
        w.push_off_bonus.weight = r.push_off_bonus_scale if shaping else 0.0
        w.landing_bonus.weight = r.landing_bonus_scale if shaping else 0.0
        w.alternating_landing_bonus.weight = r.alternating_landing_bonus_scale if shaping else 0.0
        w.left_landing_bonus.weight = r.left_landing_bonus_scale if shaping else 0.0
        w.left_single_support_bonus.weight = r.left_single_support_bonus_scale if shaping else 0.0
        w.foot_swap_bonus.weight = r.foot_swap_bonus_scale if shaping else 0.0
        w.swing_clearance_bonus.weight = r.swing_clearance_bonus_scale if shaping else 0.0
        w.duration_bonus.weight = r.duration_bonus_scale if (shaping and r.enable_duration_bonus) else 0.0
        w.displacement_milestone_bonus.weight = 1.0 if (shaping and r.enable_displacement_milestones) else 0.0
        w.survival_milestone_bonus.weight = 1.0 if (shaping and r.enable_survival_milestones) else 0.0
        w.alive_bonus.weight = r.alive_bonus_scale if (shaping and r.enable_alive_bonus) else 0.0
        w.displacement_progress_bonus.weight = r.displacement_progress_scale if (
            shaping and r.enable_displacement_progress_bonus
        ) else 0.0
        w.long_horizon_bonus.weight = r.long_horizon_bonus_scale if (shaping and r.enable_long_horizon_bonus) else 0.0

        posture = r.enable_posture_penalties
        w.backward_lean_penalty.weight = -r.lean_backward_penalty_scale if posture else 0.0
        w.forward_lean_penalty.weight = -r.lean_forward_penalty_scale if posture else 0.0
        w.double_support_forward_lean_penalty.weight = -r.ds_forward_lean_penalty_scale if posture else 0.0
        w.fall_forward_penalty.weight = -r.fall_forward_penalty_scale if posture else 0.0
        w.same_side_streak_penalty.weight = -r.same_side_streak_penalty_scale if posture else 0.0
        w.contact_imbalance_penalty.weight = -r.contact_imbalance_penalty_scale if posture else 0.0
        w.right_pivot_penalty.weight = -r.right_pivot_penalty_scale if posture else 0.0
        w.backward_dx_penalty.weight = -r.backward_dx_penalty_scale if posture else 0.0
        w.lateral_velocity_penalty.weight = -r.lateral_vel_penalty_scale if posture else 0.0
        w.angular_velocity_penalty.weight = -r.ang_vel_penalty_scale if posture else 0.0
        w.action_rate_penalty.weight = -r.action_rate_penalty_scale if posture else 0.0
        w.imu_height_penalty.weight = -r.imu_height_penalty_scale if posture else 0.0
        w.flight_duration_penalty.weight = -r.aerial_duration_penalty_scale if (posture and r.enable_flight_duration) else 0.0
        w.knee_hyperflex_penalty.weight = -r.knee_hyperflex_penalty_scale if posture else 0.0
        w.heading_misalign_penalty.weight = -r.heading_misalign_penalty_scale if posture else 0.0
        w.lateral_tilt_penalty.weight = -r.lateral_tilt_penalty_scale if posture else 0.0
        w.double_support_penalty.weight = -r.double_support_penalty_scale if (posture and r.enable_double_support) else 0.0
        w.effort_penalty.weight = -1.0 if r.enable_effort else 0.0


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
