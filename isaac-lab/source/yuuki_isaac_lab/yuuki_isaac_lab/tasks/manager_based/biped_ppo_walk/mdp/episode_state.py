# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Biped walk episode state (ported from Direct env buffers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch
from isaaclab.utils.math import quat_apply

from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import action as action_mdp
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import episode_state as episode_mdp
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import pose as pose_mdp
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import termination as termination_mdp
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp.actuators import (
    FOOT_SITE_OFFSET,
    HEEL_SITE_OFFSET,
    IMU_OFFSET,
    JOINT_NAMES,
    LEFT_SOLE_BODY,
    RIGHT_SOLE_BODY,
    ROOT_BODY_NAME,
    TOE_SITE_OFFSET,
    ctrl_ranges_tensor,
)

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


@dataclass
class BipedStepSnapshot:
    """Physics and gait-phase snapshot for one control step."""

    physics: dict[str, torch.Tensor]
    biped: episode_mdp.BipedStepContext
    dx: torch.Tensor
    left_foot_dx: torch.Tensor
    right_foot_dx: torch.Tensor
    progress_m: torch.Tensor
    imu_dz: torch.Tensor


class BipedEpisodeState:
    """Episode buffers shared across Manager terms."""

    def __init__(self, env: ManagerBasedRLEnv) -> None:
        self._env = env
        self._device = env.device
        self._num_envs = env.num_envs

        robot = env.scene["robot"]
        found_ids, found_names = robot.find_joints(list(JOINT_NAMES))
        name_to_id = {name: idx for name, idx in zip(found_names, found_ids, strict=True)}
        self.joint_ids = [name_to_id[name] for name in JOINT_NAMES]

        self.root_body_id = robot.find_bodies(ROOT_BODY_NAME)[0][0]
        self.left_sole_id = robot.find_bodies(LEFT_SOLE_BODY)[0][0]
        self.right_sole_id = robot.find_bodies(RIGHT_SOLE_BODY)[0][0]
        self.left_knee_id = robot.find_joints("left_knee_pitch")[0][0]
        self.right_knee_id = robot.find_joints("right_knee_pitch")[0][0]

        self.ctrl_lo, self.ctrl_hi = ctrl_ranges_tensor(self._device)
        self.joint_lo = self.ctrl_lo.clone()
        self.joint_hi = self.ctrl_hi.clone()

        self.foot_off = torch.tensor(FOOT_SITE_OFFSET, device=self._device, dtype=torch.float32)
        self.heel_off = torch.tensor(HEEL_SITE_OFFSET, device=self._device, dtype=torch.float32)
        self.toe_off = torch.tensor(TOE_SITE_OFFSET, device=self._device, dtype=torch.float32)
        self.imu_off = torch.tensor(IMU_OFFSET, device=self._device, dtype=torch.float32)

        n = self._num_envs
        self.prev_imu_x = torch.zeros(n, device=self._device)
        self.prev_left_foot_x = torch.zeros(n, device=self._device)
        self.prev_right_foot_x = torch.zeros(n, device=self._device)
        self.prev_imu_z = torch.zeros(n, device=self._device)
        self.prev_left_on_floor = torch.zeros(n, device=self._device, dtype=torch.bool)
        self.prev_right_on_floor = torch.zeros(n, device=self._device, dtype=torch.bool)
        self.prev_single_support_side = torch.zeros(n, device=self._device, dtype=torch.long)
        self.aerial_steps = torch.zeros(n, device=self._device, dtype=torch.long)
        self.same_side_streak = torch.zeros(n, device=self._device, dtype=torch.long)
        self.best_imu_x = torch.zeros(n, device=self._device)
        self.prev_action = torch.zeros(n, len(JOINT_NAMES), device=self._device)
        self.prev_step_action = torch.zeros(n, len(JOINT_NAMES), device=self._device)
        self.episode_start_imu_x = torch.zeros(n, device=self._device)
        self.last_episode_displacement = torch.zeros(n, device=self._device)
        self.milestone_level = torch.zeros(n, device=self._device, dtype=torch.long)
        self.survival_milestone_level = torch.zeros(n, device=self._device, dtype=torch.long)
        self.bad_pose_steps = torch.zeros(n, device=self._device, dtype=torch.long)

        self.snapshot: BipedStepSnapshot | None = None
        self._last_update_step: int = -1

        self._last_physics: dict[str, torch.Tensor] | None = None
        self._last_biped_ctx: episode_mdp.BipedStepContext | None = None

    def read_physics_state(self) -> dict[str, torch.Tensor]:
        """Read IMU, foot sites, and pose metrics (same as Direct env)."""
        robot = self._env.scene["robot"]
        root_pos = robot.data.body_pos_w[:, self.root_body_id]
        root_quat = robot.data.body_quat_w[:, self.root_body_id]
        root_ang_vel = robot.data.body_ang_vel_w[:, self.root_body_id]

        left_pos = robot.data.body_pos_w[:, self.left_sole_id]
        left_quat = robot.data.body_quat_w[:, self.left_sole_id]
        right_pos = robot.data.body_pos_w[:, self.right_sole_id]
        right_quat = robot.data.body_quat_w[:, self.right_sole_id]

        n = self._num_envs
        imu_pos = root_pos + quat_apply(root_quat, self.imu_off.unsqueeze(0).expand(n, -1))
        left_foot = left_pos + quat_apply(left_quat, self.foot_off.unsqueeze(0).expand(n, -1))
        right_foot = right_pos + quat_apply(right_quat, self.foot_off.unsqueeze(0).expand(n, -1))
        left_toe = left_pos + quat_apply(left_quat, self.toe_off.unsqueeze(0).expand(n, -1))
        left_heel = left_pos + quat_apply(left_quat, self.heel_off.unsqueeze(0).expand(n, -1))
        right_toe = right_pos + quat_apply(right_quat, self.toe_off.unsqueeze(0).expand(n, -1))
        right_heel = right_pos + quat_apply(right_quat, self.heel_off.unsqueeze(0).expand(n, -1))

        imu_zaxis = pose_mdp.imu_zaxis_world(root_quat)
        body_x = pose_mdp.body_xaxis_world(root_quat)
        lean_fwd_body, heading_align, tilt_horiz = pose_mdp.pose_metrics(imu_zaxis, body_x)
        upright = imu_zaxis[:, 2]

        term_cfg = self._env.cfg.termination
        left_on = termination_mdp.foot_contact_from_heights(
            left_foot[:, 2], left_toe[:, 2], left_heel[:, 2], term_cfg.foot_contact_z_on, term_cfg.foot_contact_z_off
        )
        right_on = termination_mdp.foot_contact_from_heights(
            right_foot[:, 2], right_toe[:, 2], right_heel[:, 2], term_cfg.foot_contact_z_on, term_cfg.foot_contact_z_off
        )

        root_vel = robot.data.root_lin_vel_w[:, :3]

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
            "left_knee": robot.data.joint_pos[:, self.left_knee_id],
            "right_knee": robot.data.joint_pos[:, self.right_knee_id],
            "left_knee_vel": robot.data.joint_vel[:, self.left_knee_id],
            "right_knee_vel": robot.data.joint_vel[:, self.right_knee_id],
        }

    def update_after_physics(self) -> None:
        """Update gait phase, progress, and step snapshot after physics."""
        physics = self.read_physics_state()
        self._last_physics = physics

        dx = physics["imu_x"] - self.prev_imu_x
        left_foot_dx = physics["left_foot_x"] - self.prev_left_foot_x
        right_foot_dx = physics["right_foot_x"] - self.prev_right_foot_x

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

        reward_cfg = self._env.cfg.reward
        progress_m, self.best_imu_x = episode_mdp.advance_progress(
            physics["imu_x"],
            self.best_imu_x,
            upright=physics["upright"],
            single_support=biped_ctx.single_support,
            progress_min_upright=reward_cfg.progress_min_upright,
            progress_require_single_support=reward_cfg.progress_require_single_support,
        )
        imu_dz = physics["imu_z"] - self.prev_imu_z

        self.prev_step_action = self.prev_action.clone()
        raw = self._env.action_manager.action
        self.prev_action = action_mdp.clip_policy_action(raw).clone()

        self.snapshot = BipedStepSnapshot(
            physics=physics,
            biped=biped_ctx,
            dx=dx,
            left_foot_dx=left_foot_dx,
            right_foot_dx=right_foot_dx,
            progress_m=progress_m,
            imu_dz=imu_dz,
        )

        self.prev_imu_x = physics["imu_x"].clone()
        self.prev_left_foot_x = physics["left_foot_x"].clone()
        self.prev_right_foot_x = physics["right_foot_x"].clone()
        self.prev_imu_z = physics["imu_z"].clone()

        self._last_update_step = int(self._env.common_step_counter)

    def record_episode_displacement(self, env_ids: torch.Tensor) -> None:
        """Store +X displacement before reset (eval_biped_walk.py compat)."""
        if env_ids.numel() == 0 or self.snapshot is None:
            return
        displacement = self.snapshot.physics["imu_x"][env_ids] - self.episode_start_imu_x[env_ids]
        self.last_episode_displacement[env_ids] = displacement
        self._env.extras.setdefault("log", {})
        self._env.extras["log"]["Metrics/episode_displacement_x"] = displacement.mean()

    def init_env_buffers(self, env_ids: torch.Tensor) -> None:
        """Init episode buffers from post-reset physics."""
        if env_ids.numel() == 0:
            return

        physics = self.read_physics_state()
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


def get_biped_state(env: ManagerBasedRLEnv) -> BipedEpisodeState:
    state = getattr(env, "biped_state", None)
    if state is None:
        raise RuntimeError("BipedEpisodeState is not initialized on the environment.")
    return state


def ensure_step_updated(env: ManagerBasedRLEnv) -> BipedStepSnapshot:
    """Update physics/gait state once per control step and return snapshot."""
    state = get_biped_state(env)
    if state._last_update_step != int(env.common_step_counter):
        state.update_after_physics()
    if state.snapshot is None:
        raise RuntimeError("Biped step snapshot is unavailable after update.")
    return state.snapshot
