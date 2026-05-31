"""exp_008: 片脚ホッパ向け Gym 風環境ラッパー。

ロボットは model/main.xml のモノポッド 1 脚（freejoint）。両脚歩行ではない。
"""

import time

import mujoco
import mujoco.viewer
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

import config
from episode_state import EpisodeState
from observation import Observation
from effort import EffortTracker
from reward import Reward
from termination import (
  NOT_TERMINATED,
  REASON_CONTACT_BASKET,
  REASON_CONTACT_THIGH,
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_BACKWARD_LEAN,
  Termination,
)
from lib.action import ActionBinding


class Env2JointPPO:
  """exp_008 用環境（片脚ホッパ・足底幾何観測 25 次元）。"""

  def __init__(self, *, enable_viewer: bool = True):
    self.model = mujoco.MjModel.from_xml_path(config.XML_PATH)
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)

    physics_dt = float(self.model.opt.timestep)
    if abs(physics_dt - config.PHYSICS_TIMESTEP_S) > 1e-9:
      raise ValueError(
        f"model.opt.timestep={physics_dt} != config.PHYSICS_TIMESTEP_S={config.PHYSICS_TIMESTEP_S}"
      )

    self.viewer = None
    if enable_viewer:
      self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
      apply_passive_viewer_options(self.viewer)

    self._episode = EpisodeState()
    self._action = ActionBinding(self.model)
    self._observation = Observation(self.model)
    self._reward = Reward()
    self._effort = EffortTracker(self.model)
    self._termination = Termination(self.model)

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    if self.viewer is not None:
      self.viewer.sync()

    imu_x = float(self.data.site("imu_site").xpos[0])
    imu_z = float(self.data.site("imu_site").xpos[2])
    foot_x = float(self.data.site("foot_site").xpos[0])
    self._episode.reset_forward_tracking(imu_x=imu_x, foot_x=foot_x, imu_z=imu_z)
    self._episode.prev_action = (0.0, 0.0)

    # policy_obs: 正規化済み 25 次元（ポリシー入力）。reset 時は報酬用 step_physics は不要。
    policy_obs, _ = self._observation.build(
      self.model, self.data, self._episode, dx=0.0, foot_dx=0.0
    )
    return policy_obs.to_vector()

  def step(self, action, visualize: bool = False, episode_step: int = 0):
    prev_action = self._action.apply(self.data, action)

    termination = NOT_TERMINATED
    shank_penalty_sum = 0.0
    self._effort.reset_control_step()
    for _ in range(config.FRAME_SKIP):
      mujoco.mj_step(self.model, self.data)
      self._effort.record_physics_step(self.data)
      if self.viewer is not None:
        self.viewer.sync()

      termination = self._termination.done_reason_contact(self.data)
      if termination.terminated:
        break

      shank_penalty_sum += self._termination.shank_contact_step_penalty(self.data)

    effort = self._effort.control_step_breakdown()

    if visualize:
      time.sleep(config.CONTROL_TIMESTEP_S)

    imu_x = float(self.data.site("imu_site").xpos[0])
    imu_z = float(self.data.site("imu_site").xpos[2])
    foot_x = float(self.data.site("foot_site").xpos[0])
    dx = self._episode.advance_imu_x(imu_x)
    foot_dx = self._episode.advance_foot_x(foot_x)

    # policy_obs … 正規化済み観測（エージェントへ返す）
    # step_physics … 生の物理量（報酬・終了判定・step_info 用）
    policy_obs, step_physics = self._observation.build(
      self.model, self.data, self._episode, dx=dx, foot_dx=foot_dx
    )

    hop = self._episode.advance_hop_context(
      foot_on_floor=step_physics.foot_on_floor, imu_z=imu_z
    )
    progress_m = self._episode.advance_progress(
      imu_x, upright=step_physics.upright
    )

    reward_breakdown = self._reward.compute(
      step_physics, hop=hop, effort=effort, progress_m=progress_m
    )

    if not termination.terminated:
      termination = self._termination.done_reason_pose(
        step_physics, foot_on_floor=step_physics.foot_on_floor
      )

    terminated = termination.terminated
    termination_reason = termination.reason

    reward = (
      reward_breakdown.total
      + termination.penalty
      + shank_penalty_sum
    )

    self._episode.prev_action = prev_action

    contact_force_n = termination.contact_normal_force_n
    step_info = {
      "upright": step_physics.upright,
      "foot_on_floor": float(step_physics.foot_on_floor),
      "flight_steps": float(hop.flight_steps),
      "landed": float(hop.landed),
      "reward_forward": reward_breakdown.forward,
      "reward_forward_imu": reward_breakdown.forward_imu,
      "reward_forward_foot": reward_breakdown.forward_foot,
      "reward_shaping": reward_breakdown.shaping,
      "reward_upright": reward_breakdown.upright_bonus,
      "reward_push_off": reward_breakdown.push_off_bonus,
      "reward_landing": reward_breakdown.landing_bonus,
      "reward_backward_lean_penalty": reward_breakdown.backward_lean_penalty,
      "reward_forward_lean_penalty": reward_breakdown.forward_lean_penalty,
      "reward_height_penalty": reward_breakdown.height_penalty,
      "reward_flight_duration_penalty": reward_breakdown.flight_duration_penalty,
      "reward_progress": reward_breakdown.progress_bonus,
      "reward_knee_hyperflex_penalty": reward_breakdown.knee_hyperflex_penalty,
      "reward_flight_low_upright_penalty": reward_breakdown.flight_low_upright_penalty,
      "reward_hop_dx_band": reward_breakdown.hop_dx_band_bonus,
      "reward_survival": reward_breakdown.survival_bonus,
      "foot_dx": step_physics.foot_dx,
      "reward_effort_penalty": reward_breakdown.effort_penalty,
      "effort_power_cost": reward_breakdown.effort_power_cost,
      "reward_shank_step_penalty": shank_penalty_sum,
      "reward_termination_penalty": termination.penalty,
      "reward_contact_basket_penalty": (
        termination.penalty if termination_reason == REASON_CONTACT_BASKET else 0.0
      ),
      "reward_contact_thigh_penalty": (
        termination.penalty if termination_reason == REASON_CONTACT_THIGH else 0.0
      ),
      "reward_contact_shank_penalty": shank_penalty_sum,
      "reward_pose_penalty": (
        termination.penalty
        if termination_reason
        in (REASON_IMU_Z, REASON_LOW_UPRIGHT, REASON_BACKWARD_LEAN)
        else 0.0
      ),
      "reward_fall_penalty": (
        termination.penalty
        if termination_reason
        in (REASON_IMU_Z, REASON_LOW_UPRIGHT, REASON_BACKWARD_LEAN)
        else 0.0
      ),
      "termination_reason": termination_reason,
      "contact_normal_force_n": contact_force_n,
      "basket_contact_normal_force_n": (
        contact_force_n if termination_reason == REASON_CONTACT_BASKET else None
      ),
      "thigh_contact_normal_force_n": (
        contact_force_n if termination_reason == REASON_CONTACT_THIGH else None
      ),
    }

    return policy_obs.to_vector(), reward, terminated, step_info
