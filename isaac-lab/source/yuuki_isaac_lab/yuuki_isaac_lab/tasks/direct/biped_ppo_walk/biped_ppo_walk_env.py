# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""exp_030 両脚交互片脚歩行 PPO の Isaac Lab DirectRLEnv 実装。"""

from __future__ import annotations

from collections.abc import Sequence

import torch

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation
from isaaclab.envs import DirectRLEnv
from isaaclab.sim.spawners.from_files import GroundPlaneCfg, spawn_ground_plane
from isaaclab.utils.math import quat_apply

from yuuki_isaac_lab.assets.robots.yuuki_biped.mjcf_utils import ensure_mjcf_importer_enabled

from .biped_ppo_walk_env_cfg import BipedPpoWalkEnvCfg, get_max_dx_per_step, get_max_foot_dx_per_step
from .mdp import action as action_mdp
from .mdp import episode_state as episode_mdp
from .mdp import obs_norm
from .mdp import pose as pose_mdp
from .mdp import reward as reward_mdp
from .mdp import termination as termination_mdp
from .mdp.actuators import (
    FOOT_SITE_OFFSET,
    HEEL_SITE_OFFSET,
    IMU_OFFSET,
    LEFT_SOLE_BODY,
    RIGHT_SOLE_BODY,
    ROOT_BODY_NAME,
    TOE_SITE_OFFSET,
    ctrl_ranges_tensor,
    neutral_pos_tensor,
)


class BipedPpoWalkEnv(DirectRLEnv):
    """両脚 12 DOF・観測 54 次元・+X 交互片脚歩行（exp_030 移植）。"""

    cfg: BipedPpoWalkEnvCfg

    def __init__(self, cfg: BipedPpoWalkEnvCfg, render_mode: str | None = None, **kwargs):
        # headless kit では MJCF インポータが未ロードのため、spawn 前に有効化する
        ensure_mjcf_importer_enabled()
        super().__init__(cfg, render_mode, **kwargs)

        # 関節インデックス（exp_030 JOINT_NAMES 順を保証）
        found_ids, found_names = self.robot.find_joints(list(self.cfg.joint_names))
        name_to_id = {name: idx for name, idx in zip(found_names, found_ids, strict=True)}
        self._joint_ids = [name_to_id[name] for name in self.cfg.joint_names]

        # ボディインデックス
        self._root_body_id = self.robot.find_bodies(ROOT_BODY_NAME)[0][0]
        self._left_sole_id = self.robot.find_bodies(LEFT_SOLE_BODY)[0][0]
        self._right_sole_id = self.robot.find_bodies(RIGHT_SOLE_BODY)[0][0]

        # 膝関節（報酬・観測用）
        self._left_knee_id = self.robot.find_joints("left_knee_pitch")[0][0]
        self._right_knee_id = self.robot.find_joints("right_knee_pitch")[0][0]

        # 行動写像用テンソル
        self._ctrl_lo, self._ctrl_hi = ctrl_ranges_tensor(self.device)
        self._neutral_pos = neutral_pos_tensor(self.device)

        # 関節角正規化レンジ
        self._joint_lo = self._ctrl_lo.clone()
        self._joint_hi = self._ctrl_hi.clone()

        # sole ローカルオフセット（site 近似）
        self._foot_off = torch.tensor(FOOT_SITE_OFFSET, device=self.device, dtype=torch.float32)
        self._heel_off = torch.tensor(HEEL_SITE_OFFSET, device=self.device, dtype=torch.float32)
        self._toe_off = torch.tensor(TOE_SITE_OFFSET, device=self.device, dtype=torch.float32)
        self._imu_off = torch.tensor(IMU_OFFSET, device=self.device, dtype=torch.float32)

        # エピソード状態バッファ
        n = self.num_envs
        self.prev_imu_x = torch.zeros(n, device=self.device)
        self.prev_left_foot_x = torch.zeros(n, device=self.device)
        self.prev_right_foot_x = torch.zeros(n, device=self.device)
        self.prev_imu_z = torch.zeros(n, device=self.device)
        self.prev_left_on_floor = torch.zeros(n, device=self.device, dtype=torch.bool)
        self.prev_right_on_floor = torch.zeros(n, device=self.device, dtype=torch.bool)
        self.prev_single_support_side = torch.zeros(n, device=self.device, dtype=torch.long)
        self.aerial_steps = torch.zeros(n, device=self.device, dtype=torch.long)
        # 同じ片脚側が連続する degenerate gait 検出用（交互歩行 shaping）
        self.same_side_streak = torch.zeros(n, device=self.device, dtype=torch.long)
        self.best_imu_x = torch.zeros(n, device=self.device)
        self.prev_action = torch.zeros(n, self.cfg.action_space, device=self.device)
        self.prev_step_action = torch.zeros(n, self.cfg.action_space, device=self.device)
        # エピソード開始時 IMU X（移動距離計測用）
        self.episode_start_imu_x = torch.zeros(n, device=self.device)
        # 直近終了エピソードの +X 移動距離（eval_biped_walk.py 用）
        self.last_episode_displacement = torch.zeros(n, device=self.device)
        # 累積移動距離マイルストーン（2/5/10/15 m）の到達済みレベル
        self.milestone_level = torch.zeros(n, device=self.device, dtype=torch.long)
        self.survival_milestone_level = torch.zeros(n, device=self.device, dtype=torch.long)
        # 連続姿勢異常ステップ（ヒステリシス付き早期終了）
        self.bad_pose_steps = torch.zeros(n, device=self.device, dtype=torch.long)

        # 直近ステップの物理量（報酬計算用）
        self._last_dx = torch.zeros(n, device=self.device)
        self._last_left_foot_dx = torch.zeros(n, device=self.device)
        self._last_right_foot_dx = torch.zeros(n, device=self.device)
        self._last_biped_ctx: episode_mdp.BipedStepContext | None = None
        self._last_progress_m = torch.zeros(n, device=self.device)
        self._last_imu_dz = torch.zeros(n, device=self.device)
        self._last_physics: dict[str, torch.Tensor] = {}

    def _setup_scene(self) -> None:
        """ロボット・地面・照明を配置する（replicate_physics 向けに articulation を clone 前に登録）。"""
        self.robot = Articulation(self.cfg.robot_cfg)
        self.scene.articulations["robot"] = self.robot
        spawn_ground_plane(prim_path="/World/ground", cfg=GroundPlaneCfg())
        self.scene.clone_environments(copy_from_source=False)
        # replicate_physics=True + GPU では衝突フィルタは自動。CPU のみ手動設定
        if self.device == "cpu":
            self.scene.filter_collisions(global_prim_paths=["/World/ground"])

        light_cfg = sim_utils.DomeLightCfg(intensity=2000.0, color=(0.75, 0.75, 0.75))
        light_cfg.func("/World/Light", light_cfg)

    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        # 前ステップの clipped action を保持（行動変化率ペナルティ用）
        self.prev_step_action = self.prev_action.clone()
        self.actions = actions.clone()

    def _apply_action(self) -> None:
        """ポリシー出力を関節位置目標に写像して適用する。"""
        targets = action_mdp.actions_to_joint_targets(
            self.actions, self._ctrl_lo, self._ctrl_hi, self._neutral_pos
        )
        self.robot.set_joint_position_target(targets, joint_ids=self._joint_ids)
        self.prev_action = action_mdp.clip_policy_action(self.actions).clone()

    def _get_observations(self) -> dict:
        """54 次元観測（51 次元 + 歩行位相 3 次元）を構築する。"""
        physics = self._read_physics_state()
        self._last_physics = physics

        dx = physics["imu_x"] - self.prev_imu_x
        left_foot_dx = physics["left_foot_x"] - self.prev_left_foot_x
        right_foot_dx = physics["right_foot_x"] - self.prev_right_foot_x

        self._last_dx = dx
        self._last_left_foot_dx = left_foot_dx
        self._last_right_foot_dx = right_foot_dx

        (
            biped_ctx,
            self.prev_left_on_floor,
            self.prev_right_on_floor,
            self.prev_single_support_side,
            self.aerial_steps,
            self.same_side_streak,
        ) = episode_mdp.advance_biped_context(
            left_on_floor=physics["left_on_floor"],
            right_on_floor=physics["right_on_floor"],
            prev_left_on_floor=self.prev_left_on_floor,
            prev_right_on_floor=self.prev_right_on_floor,
            prev_single_support_side=self.prev_single_support_side,
            aerial_steps=self.aerial_steps,
            same_side_streak=self.same_side_streak,
            imu_z=physics["imu_z"],
            prev_imu_z=self.prev_imu_z,
        )
        self._last_biped_ctx = biped_ctx

        progress_m, self.best_imu_x = episode_mdp.advance_progress(
            physics["imu_x"],
            self.best_imu_x,
            upright=physics["upright"],
            single_support=biped_ctx.single_support,
            progress_min_upright=self.cfg.reward.progress_min_upright,
            progress_require_single_support=self.cfg.reward.progress_require_single_support,
        )
        self._last_progress_m = progress_m
        self._last_imu_dz = physics["imu_z"] - self.prev_imu_z

        # 観測ベクトル組み立て
        joint_q = self.robot.data.joint_pos[:, self._joint_ids]
        joint_qvel = self.robot.data.joint_vel[:, self._joint_ids]
        joint_q_norm = obs_norm.range_to_norm(joint_q, self._joint_lo, self._joint_hi)
        joint_qvel_norm = obs_norm.clip_scale(joint_qvel, self.cfg.max_joint_vel_rad_s)

        support_side_obs = biped_ctx.single_support_side.float().unsqueeze(-1)
        streak_norm = torch.clamp(biped_ctx.same_side_streak.float() / 40.0, max=1.0).unsqueeze(-1)
        ep_progress = (self.episode_length_buf.float() / float(self.max_episode_length)).unsqueeze(-1)

        obs = torch.cat(
            [
                obs_norm.clip_scale(dx, get_max_dx_per_step(self.cfg)).unsqueeze(-1),
                obs_norm.clip_scale(physics["imu_gyro"], self.cfg.max_gyro_rad_s),
                physics["imu_zaxis"],
                obs_norm.height_to_norm(physics["imu_z"], self.cfg.min_imu_z_norm, self.cfg.max_imu_z).unsqueeze(-1),
                torch.where(physics["left_on_floor"], torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1),
                torch.where(physics["right_on_floor"], torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1),
                obs_norm.clip_scale(left_foot_dx, get_max_foot_dx_per_step(self.cfg)).unsqueeze(-1),
                obs_norm.clip_scale(right_foot_dx, get_max_foot_dx_per_step(self.cfg)).unsqueeze(-1),
                obs_norm.height_to_norm(physics["left_foot_z"], self.cfg.min_foot_z_norm, self.cfg.max_foot_z_norm).unsqueeze(
                    -1
                ),
                obs_norm.height_to_norm(physics["right_foot_z"], self.cfg.min_foot_z_norm, self.cfg.max_foot_z_norm).unsqueeze(
                    -1
                ),
                torch.where(biped_ctx.single_support, torch.ones_like(dx), -torch.ones_like(dx)).unsqueeze(-1),
                joint_q_norm,
                joint_qvel_norm,
                self.prev_action,
                support_side_obs,
                streak_norm,
                ep_progress,
            ],
            dim=-1,
        )

        # 次ステップ用に位置を更新
        self.prev_imu_x = physics["imu_x"].clone()
        self.prev_left_foot_x = physics["left_foot_x"].clone()
        self.prev_right_foot_x = physics["right_foot_x"].clone()
        self.prev_imu_z = physics["imu_z"].clone()

        return {"policy": obs}

    def _update_pose_hysteresis(self, physics: dict[str, torch.Tensor]) -> torch.Tensor:
        """連続姿勢異常カウントを更新し、終了フラグを返す。"""
        pose_bad, _ = termination_mdp.compute_pose_termination(
            imu_z=physics["imu_z"],
            upright=physics["upright"],
            lean_fwd_body=physics["lean_fwd_body"],
            both_feet_on_floor=physics["left_on_floor"] & physics["right_on_floor"],
            min_imu_z=self.cfg.termination.min_imu_z,
            min_imu_upright=self.cfg.termination.min_imu_upright,
            max_backward_lean_body=self.cfg.termination.max_backward_lean_body,
            max_forward_lean_both_feet=self.cfg.termination.max_forward_lean_both_feet,
            pose_termination_penalty=self.cfg.termination.pose_termination_penalty,
        )
        self.bad_pose_steps = torch.where(
            pose_bad,
            self.bad_pose_steps + 1,
            torch.zeros_like(self.bad_pose_steps),
        )
        return self.bad_pose_steps >= self.cfg.termination.bad_pose_consecutive_steps

    def _get_rewards(self) -> torch.Tensor:
        """ステップ報酬を計算する。"""
        physics = self._last_physics
        biped = self._last_biped_ctx
        if not physics or biped is None:
            return torch.zeros(self.num_envs, device=self.device)

        pose_done = self._update_pose_hysteresis(physics)

        effort_penalty = reward_mdp.compute_effort_penalty(
            self.robot.data.applied_torque[:, self._joint_ids],
            self.robot.data.joint_vel[:, self._joint_ids],
            dt=self.cfg.sim.dt * float(self.cfg.decimation),
            scale=self.cfg.reward.effort_penalty_scale,
        )

        reward, forward, effort, self.milestone_level, self.survival_milestone_level = reward_mdp.compute_step_reward(
            cfg=self.cfg.reward,
            max_dx_per_step=get_max_dx_per_step(self.cfg),
            dx=self._last_dx,
            root_vel_x=physics["root_vel_x"],
            left_foot_dx=self._last_left_foot_dx,
            right_foot_dx=self._last_right_foot_dx,
            upright=physics["upright"],
            lean_fwd_body=physics["lean_fwd_body"],
            heading_align=physics["heading_align"],
            tilt_horiz=physics["tilt_horiz"],
            imu_z=physics["imu_z"],
            left_foot_z=physics["left_foot_z"],
            right_foot_z=physics["right_foot_z"],
            left_knee=physics["left_knee"],
            right_knee=physics["right_knee"],
            biped=biped,
            progress_m=self._last_progress_m,
            imu_dz=self._last_imu_dz,
            left_knee_vel=physics["left_knee_vel"],
            right_knee_vel=physics["right_knee_vel"],
            left_toe_z=physics["left_toe_z"],
            left_heel_z=physics["left_heel_z"],
            right_toe_z=physics["right_toe_z"],
            right_heel_z=physics["right_heel_z"],
            effort_penalty=effort_penalty,
            imu_gyro=physics["imu_gyro"],
            root_vel_y=physics["root_vel_y"],
            episode_step=self.episode_length_buf,
            max_episode_steps=self.max_episode_length,
            total_displacement=physics["imu_x"] - self.episode_start_imu_x,
            milestone_level=self.milestone_level,
            survival_milestone_level=self.survival_milestone_level,
            current_action=action_mdp.clip_policy_action(self.actions),
            prev_step_action=self.prev_step_action,
        )

        # RSL-RL → TensorBoard: iteration 内の rollout ステップ平均として記録される
        self.extras["log"] = {
            "Reward/mean_forward": forward.mean(),
            "Reward/mean_effort": effort.mean(),
            "Metrics/mean_imu_x": physics["imu_x"].mean(),
            "Metrics/mean_root_vel_x": physics["root_vel_x"].mean(),
            "Metrics/mean_upright": physics["upright"].mean(),
            "Metrics/mean_imu_z": physics["imu_z"].mean(),
            "Metrics/left_contact_ratio": physics["left_on_floor"].float().mean(),
            "Metrics/right_contact_ratio": physics["right_on_floor"].float().mean(),
            "Metrics/single_support_ratio": biped.single_support.float().mean(),
            "Metrics/mean_left_foot_z": physics["left_foot_z"].mean(),
            "Metrics/mean_right_foot_z": physics["right_foot_z"].mean(),
            "Metrics/term_low_z_ratio": (physics["imu_z"] < self.cfg.termination.min_imu_z).float().mean(),
            "Metrics/term_low_upright_ratio": (
                physics["upright"] < self.cfg.termination.min_imu_upright
            ).float().mean(),
            "Metrics/mean_lean_fwd": physics["lean_fwd_body"].mean(),
            "Metrics/both_feet_ratio": (physics["left_on_floor"] & physics["right_on_floor"]).float().mean(),
            "Metrics/mean_same_side_streak": biped.same_side_streak.float().mean(),
            "Metrics/alternating_landing_ratio": biped.alternating_landing.float().mean(),
            "Metrics/right_single_support_ratio": (
                biped.single_support & (biped.single_support_side == -1)
            ).float().mean(),
            "Metrics/foot_swap_ratio": biped.foot_swap.float().mean(),
            "Metrics/mean_milestone_level": self.milestone_level.float().mean(),
            "Metrics/mean_survival_milestone_level": self.survival_milestone_level.float().mean(),
            "Metrics/mean_bad_pose_steps": self.bad_pose_steps.float().mean(),
        }

        # 姿勢終了ペナルティはエピソード終了時のみ（毎ステップ -30 は学習を破壊する）
        pose_term, pose_penalty = termination_mdp.compute_pose_termination(
            imu_z=physics["imu_z"],
            upright=physics["upright"],
            lean_fwd_body=physics["lean_fwd_body"],
            both_feet_on_floor=physics["left_on_floor"] & physics["right_on_floor"],
            min_imu_z=self.cfg.termination.min_imu_z,
            min_imu_upright=self.cfg.termination.min_imu_upright,
            max_backward_lean_body=self.cfg.termination.max_backward_lean_body,
            max_forward_lean_both_feet=self.cfg.termination.max_forward_lean_both_feet,
            pose_termination_penalty=self.cfg.termination.pose_termination_penalty,
        )
        _ = pose_term
        terminal_penalty = torch.where(pose_done, pose_penalty, torch.zeros_like(reward))
        return reward + terminal_penalty

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        physics = self._last_physics
        if not physics:
            z = torch.zeros(self.num_envs, device=self.device, dtype=torch.bool)
            t = self.episode_length_buf >= self.max_episode_length - 1
            return z, t

        pose_done = self.bad_pose_steps >= self.cfg.termination.bad_pose_consecutive_steps
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        return pose_done, time_out

    def _write_robot_default_pose(self, env_ids: Sequence[int]) -> None:
        """立位 keyframe（init_state）をシミュレータへ書き戻し、制御目標も中立に合わせる。"""
        joint_pos = self.robot.data.default_joint_pos[env_ids]
        joint_vel = self.robot.data.default_joint_vel[env_ids]
        default_root_state = self.robot.data.default_root_state[env_ids].clone()
        default_root_state[:, :3] += self.scene.env_origins[env_ids]

        self.robot.write_root_pose_to_sim(default_root_state[:, :7], env_ids)
        self.robot.write_root_velocity_to_sim(default_root_state[:, 7:], env_ids)
        self.robot.write_joint_state_to_sim(joint_pos, joint_vel, None, env_ids)

        # ImplicitActuator 向け: 次ステップまでランダム行動目標が残らないよう中立姿勢を目標にする。
        self.robot.set_joint_position_target(joint_pos[:, self._joint_ids], joint_ids=self._joint_ids, env_ids=env_ids)
        self.actions[env_ids] = 0.0

        # エピソード途中リセットでも描画・バッファが即時反映されるよう同期する。
        self.scene.write_data_to_sim()
        self.sim.forward()

    def _reset_idx(self, env_ids: Sequence[int] | None) -> None:
        if env_ids is None:
            env_ids = self.robot._ALL_INDICES

        # リセット前のエピソード移動距離を記録（可視化なしの歩行評価用）
        if self._last_physics:
            if isinstance(env_ids, torch.Tensor):
                reset_ids = env_ids
            else:
                reset_ids = torch.as_tensor(list(env_ids), device=self.device, dtype=torch.long)
            if reset_ids.numel() > 0:
                displacement = self._last_physics["imu_x"][reset_ids] - self.episode_start_imu_x[reset_ids]
                self.last_episode_displacement[reset_ids] = displacement
                self.extras.setdefault("log", {})
                self.extras["log"]["Metrics/episode_displacement_x"] = displacement.mean()

        super()._reset_idx(env_ids)

        # DirectRLEnv の scene.reset() はアクチュエータのみ初期化する。
        self._write_robot_default_pose(env_ids)

        # 立位 keyframe に小さな関節角ノイズを加えて転倒耐性を高める
        noise_rad = getattr(self.cfg, "reset_joint_noise_rad", 0.0)
        if noise_rad > 0.0:
            if isinstance(env_ids, torch.Tensor):
                reset_ids = env_ids
            else:
                reset_ids = torch.as_tensor(list(env_ids), device=self.device, dtype=torch.long)
            if reset_ids.numel() > 0:
                joint_pos = self.robot.data.joint_pos[reset_ids].clone()
                joint_vel = self.robot.data.joint_vel[reset_ids].clone()
                noisy = joint_pos[:, self._joint_ids] + (torch.rand_like(joint_pos[:, self._joint_ids]) * 2.0 - 1.0) * noise_rad
                noisy = torch.clamp(noisy, self._joint_lo.unsqueeze(0), self._joint_hi.unsqueeze(0))
                joint_pos[:, self._joint_ids] = noisy
                self.robot.write_joint_state_to_sim(joint_pos, joint_vel, None, reset_ids)
                self.robot.set_joint_position_target(noisy, joint_ids=self._joint_ids, env_ids=reset_ids)

        physics = self._read_physics_state()
        self.prev_imu_x[env_ids] = physics["imu_x"][env_ids]
        self.prev_left_foot_x[env_ids] = physics["left_foot_x"][env_ids]
        self.prev_right_foot_x[env_ids] = physics["right_foot_x"][env_ids]
        self.prev_imu_z[env_ids] = physics["imu_z"][env_ids]
        self.best_imu_x[env_ids] = physics["imu_x"][env_ids]
        self.prev_left_on_floor[env_ids] = False
        self.prev_right_on_floor[env_ids] = False
        self.prev_single_support_side[env_ids] = 0
        self.aerial_steps[env_ids] = 0
        self.same_side_streak[env_ids] = 0
        self.milestone_level[env_ids] = 0
        self.survival_milestone_level[env_ids] = 0
        self.bad_pose_steps[env_ids] = 0
        self.prev_action[env_ids] = 0.0
        self.prev_step_action[env_ids] = 0.0
        self.episode_start_imu_x[env_ids] = physics["imu_x"][env_ids]

    def _read_physics_state(self) -> dict[str, torch.Tensor]:
        """IMU・足底 site 近似・姿勢量を読み出す。"""
        root_pos = self.robot.data.body_pos_w[:, self._root_body_id]
        root_quat = self.robot.data.body_quat_w[:, self._root_body_id]
        root_ang_vel = self.robot.data.body_ang_vel_w[:, self._root_body_id]

        left_pos = self.robot.data.body_pos_w[:, self._left_sole_id]
        left_quat = self.robot.data.body_quat_w[:, self._left_sole_id]
        right_pos = self.robot.data.body_pos_w[:, self._right_sole_id]
        right_quat = self.robot.data.body_quat_w[:, self._right_sole_id]

        imu_pos = root_pos + quat_apply(root_quat, self._imu_off.unsqueeze(0).expand(self.num_envs, -1))
        left_foot = left_pos + quat_apply(left_quat, self._foot_off.unsqueeze(0).expand(self.num_envs, -1))
        right_foot = right_pos + quat_apply(right_quat, self._foot_off.unsqueeze(0).expand(self.num_envs, -1))
        left_toe = left_pos + quat_apply(left_quat, self._toe_off.unsqueeze(0).expand(self.num_envs, -1))
        left_heel = left_pos + quat_apply(left_quat, self._heel_off.unsqueeze(0).expand(self.num_envs, -1))
        right_toe = right_pos + quat_apply(right_quat, self._toe_off.unsqueeze(0).expand(self.num_envs, -1))
        right_heel = right_pos + quat_apply(right_quat, self._heel_off.unsqueeze(0).expand(self.num_envs, -1))

        imu_zaxis = pose_mdp.imu_zaxis_world(root_quat)
        body_x = pose_mdp.body_xaxis_world(root_quat)
        lean_fwd_body, heading_align, tilt_horiz = pose_mdp.pose_metrics(imu_zaxis, body_x)
        upright = imu_zaxis[:, 2]

        z_on = self.cfg.termination.foot_contact_z_on
        z_off = self.cfg.termination.foot_contact_z_off
        left_on = termination_mdp.foot_contact_from_heights(
            left_foot[:, 2], left_toe[:, 2], left_heel[:, 2], z_on, z_off
        )
        right_on = termination_mdp.foot_contact_from_heights(
            right_foot[:, 2], right_toe[:, 2], right_heel[:, 2], z_on, z_off
        )

        root_vel = self.robot.data.root_lin_vel_w[:, :3]

        return {
            "imu_x": imu_pos[:, 0],
            "root_vel_x": root_vel[:, 0],
            "root_vel_y": root_vel[:, 1],
            "imu_z": imu_pos[:, 2],
            "imu_gyro": root_ang_vel,
            "imu_zaxis": imu_zaxis,
            "upright": upright,
            "lean_fwd_body": lean_fwd_body,
            "heading_align": heading_align,
            "tilt_horiz": tilt_horiz,
            "left_foot_x": left_foot[:, 0],
            "right_foot_x": right_foot[:, 0],
            "left_foot_z": left_foot[:, 2],
            "right_foot_z": right_foot[:, 2],
            "left_toe_z": left_toe[:, 2],
            "left_heel_z": left_heel[:, 2],
            "right_toe_z": right_toe[:, 2],
            "right_heel_z": right_heel[:, 2],
            "left_on_floor": left_on,
            "right_on_floor": right_on,
            "left_knee": self.robot.data.joint_pos[:, self._left_knee_id],
            "right_knee": self.robot.data.joint_pos[:, self._right_knee_id],
            "left_knee_vel": self.robot.data.joint_vel[:, self._left_knee_id],
            "right_knee_vel": self.robot.data.joint_vel[:, self._right_knee_id],
        }
