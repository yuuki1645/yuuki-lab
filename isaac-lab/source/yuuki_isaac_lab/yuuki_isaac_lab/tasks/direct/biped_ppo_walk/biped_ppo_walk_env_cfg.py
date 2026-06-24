# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""exp_030 両脚歩行 PPO 環境設定（DirectRLEnv）。"""

from __future__ import annotations

from yuuki_isaac_lab.assets.robots.yuuki_biped import YUUKI_BIPED_CFG

from isaaclab.assets import ArticulationCfg
from isaaclab.envs import DirectRLEnvCfg, ViewerCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import PhysxCfg, SimulationCfg
from isaaclab.utils import configclass
import isaaclab.sim as sim_utils

from .mdp.actuators import ACTION_DIM, FOOT_CONTACT_Z_OFF, FOOT_CONTACT_Z_ON, JOINT_NAMES


@configclass
class BipedRewardCfg:
    """exp_030 conf/reward/baseline.yaml 相当。"""

    # ENABLE 群（exp_030 conf/reward/baseline.yaml）
    enable_forward: bool = True
    # 前転時の root 速度報酬は前転ハックの温床のため無効化
    enable_forward_vel: bool = False
    enable_forward_foot: bool = True
    enable_progress: bool = True
    enable_walk_shaping: bool = True
    # shaping / upright は forward_allowed かつ最小前進量を満たすときのみ（報酬ハック抑制）
    shaping_require_forward_motion: bool = True
    shaping_min_dx: float = 0.0003
    enable_upright_bonus: bool = True
    enable_posture_penalties: bool = True
    enable_double_support: bool = True
    enable_flight_duration: bool = True
    enable_effort: bool = True
    # 転倒前の生存を促す小さなボーナス（早期エピソード終了対策）
    enable_alive_bonus: bool = True
    # v15: v14 の 0.22 は fine-tune 不安定化、v12 付近に戻し duration で生存を強化
    alive_bonus_scale: float = 0.20
    alive_min_upright: float = 0.75
    alive_min_imu_z: float = 0.50
    enable_duration_bonus: bool = True
    duration_bonus_scale: float = 0.24
    # 累積 +X 移動距離マイルストーン（1 / 2 / 5 / 10 / 15 m）
    enable_displacement_milestones: bool = True
    displacement_milestone_targets: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 15.0)
    displacement_milestone_scales: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)
    # エピソード生存ステップ数マイルストーン（v12 平均 ep ~132 のため最初の閾値を 80 に）
    enable_survival_milestones: bool = True
    survival_milestone_targets: tuple[int, ...] = (80, 150, 300, 600, 1200)
    survival_milestone_scales: tuple[float, ...] = (3.5, 4.0, 8.0, 12.0, 18.0)

    forward_reward_scale: float = 35.0
    forward_vel_reward_scale: float = 8.0
    forward_vel_max: float = 0.15

    forward_min_upright: float = 0.55
    forward_min_dx: float = 0.001
    forward_require_foot_contact: bool = True
    # 片脚支持でのみ前進報酬（前転ハック防止）
    forward_require_single_support: bool = True
    # 両足支持かつ前傾が大きいときは前進報酬を遮断
    forward_block_lean_both_feet: float = 0.07

    # 足を出さない前転ペナルティ（両足支持 + 前傾）
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
    # v12 相当（v14 の過剰強化は fine-tune 不安定化の原因）
    alternating_landing_bonus_scale: float = 1.20
    foot_swap_bonus_scale: float = 0.65
    # 右足着地を明示的に促す（v5 で右 contact ~0.02 の degenerate gait 対策）
    right_landing_bonus_scale: float = 0.75
    # 同じ片脚側が長く続くと段階ペナルティ（定常ペナルティは前進学習を阻害するため streak 連動のみ）
    same_side_streak_penalty_after: int = 18
    same_side_streak_penalty_scale: float = 0.18
    # 極端な degenerate のみ前進報酬遮断（早期学習では緩め）
    forward_block_same_side_streak: int = 48
    # 右足片脚支持＋前進を明示的に報酬（交互歩行フェーズ誘導）
    right_single_support_bonus_scale: float = 0.55
    right_single_support_min_dx: float = 0.0005
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
    progress_reward_scale: float = 35.0
    progress_min_upright: float = 0.6
    progress_require_single_support: bool = True
    knee_hyperflex_max_rad: float = 0.95
    knee_hyperflex_penalty_scale: float = 2.5
    knee_hyperflex_aerial_only: bool = True
    imu_height_penalty_scale: float = 2.0
    target_imu_z: float = 0.55
    target_imu_z_single_stance: float = 0.5
    target_imu_z_double_stance: float = 0.52
    height_penalty_aerial_crash_z: float = 0.42
    effort_penalty_scale: float = 3.0
    # v15: 転倒回復のため action rate / 横方向速度ペナルティを緩和
    action_rate_penalty_scale: float = 0.22
    lateral_vel_penalty_scale: float = 0.32
    ang_vel_penalty_scale: float = 0.04


@configclass
class BipedTerminationCfg:
    """exp_030 conf/termination/default.yaml 相当。"""

    min_imu_z: float = 0.25
    # v15: わずかに緩めて転倒判定を減らし、生存 step 延伸を優先
    min_imu_upright: float = 0.46
    max_backward_lean_body: float = 0.40
    # 両足支持のままの過度前傾で早期終了（前転歩行のハックを遮断）
    max_forward_lean_both_feet: float = 0.22
    # 瞬間的な姿勢悪化では即終了せず、連続 N ステップで終了（転倒回復の猶予）
    # v15: 姿勢回復猶予をさらに延長（v14 の 10 でも v12 未達のため）
    bad_pose_consecutive_steps: int = 12
    pose_termination_penalty: float = -30.0
    foot_contact_z_on: float = FOOT_CONTACT_Z_ON
    foot_contact_z_off: float = FOOT_CONTACT_Z_OFF


@configclass
class BipedPpoWalkEnvCfg(DirectRLEnvCfg):
    """両脚 12 DOF・観測 54 次元・+X 歩行（exp_030 移植）。"""

    # --- 制御周期: 500 Hz 物理 × decimation 10 = 50 Hz ---
    decimation = 10
    episode_length_s = 30.0

    action_space = ACTION_DIM
    # 51 + 片脚側(1) + streak_norm(1) + episode_progress(1)
    observation_space = 54
    state_space = 0

    sim: SimulationCfg = SimulationCfg(
        dt=0.002,
        render_interval=decimation,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.15,
            dynamic_friction=1.15,
            restitution=0.0,
        ),
        # 4096 env 規模の接触バッファ（RTX 4080 SUPER 16GB 向け）
        physx=PhysxCfg(
            enable_external_forces_every_iteration=True,
            solve_articulation_contact_last=True,
            min_velocity_iteration_count=1,
            gpu_max_rigid_contact_count=2**23,
            gpu_max_rigid_patch_count=2**22,
        ),
    )

    robot_cfg: ArticulationCfg = YUUKI_BIPED_CFG.replace(prim_path="/World/envs/env_.*/Robot")

    # RTX 4080 SUPER: replicate_physics + fabric clone で 4096 並列（cartpole/humanoid 同様）
    scene: InteractiveSceneCfg = InteractiveSceneCfg(
        num_envs=4096,
        env_spacing=3.0,
        replicate_physics=True,
        clone_in_fabric=True,
    )

    joint_names: tuple[str, ...] = JOINT_NAMES

    # 観測正規化（exp_030 conf/sim/default.yaml）
    max_dx_per_step_base: float = 0.05
    max_foot_dx_per_step_base: float = 0.04
    max_gyro_rad_s: float = 10.0
    max_joint_vel_rad_s: float = 10.0
    max_imu_z: float = 1.2
    min_imu_z_norm: float = 0.0
    min_foot_z_norm: float = 0.0
    max_foot_z_norm: float = 0.35

    reward: BipedRewardCfg = BipedRewardCfg()
    termination: BipedTerminationCfg = BipedTerminationCfg()
    # リセット時の関節角ランダム化 [rad]（転倒耐性・汎化）
    reset_joint_noise_rad: float = 0.025


def get_max_dx_per_step(cfg: BipedPpoWalkEnvCfg) -> float:
    """decimation 込みの最大 IMU +X 変位 [m/step]。"""
    return cfg.max_dx_per_step_base * float(cfg.decimation)


def get_max_foot_dx_per_step(cfg: BipedPpoWalkEnvCfg) -> float:
    """decimation 込みの最大足 +X 変位 [m/step]。"""
    return cfg.max_foot_dx_per_step_base * float(cfg.decimation)


@configclass
class BipedPpoWalkEnvCfg_PLAY(BipedPpoWalkEnvCfg):
    """評価・可視化向け（並列 env 数を抑える）。

    訓練用の replicate_physics + clone_in_fabric は GUI ではメッシュが env_0 のみ表示され、
    他 env は MJCF site（黄色い点）だけ見えることがあるため、play では通常 clone を使う。
    """

    scene: InteractiveSceneCfg = InteractiveSceneCfg(
        num_envs=16,
        env_spacing=4.0,
        replicate_physics=False,
        clone_in_fabric=False,
    )

    # 16 体が 4x4 に並ぶ全体を収める録画・可視化用カメラ
    viewer: ViewerCfg = ViewerCfg(
        eye=(14.0, -18.0, 9.0),
        lookat=(0.0, 0.0, 0.55),
        resolution=(1280, 720),
    )
