"""exp_018: 両脚バイペッド前進 PPO 環境（10 DOF 全サーボ）。"""

import time

import mujoco
import mujoco.viewer
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

from . import config
from .episode_state import EpisodeState
from .lib.action import ActionBinding
from .lib.actuators import LEFT_FOOT_SITE, RIGHT_FOOT_SITE
from .observation import Observation
from .effort import EffortTracker
from .reward import Reward
from .termination import (
  NOT_TERMINATED,
  REASON_CONTACT_BASKET,
  REASON_CONTACT_THIGH,
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_BACKWARD_LEAN,
  Termination,
)


class EnvBipedPPO:
  """両脚 10 DOF・観測 42 次元・+X 前進タスク。"""

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
    self._reward = Reward(self.model)
    self._effort = EffortTracker(self.model)
    self._termination = Termination(self.model)
    self._stand_key_id = mujoco.mj_name2id(
      self.model, mujoco.mjtObj.mjOBJ_KEY, "stand"
    )

  def _apply_stand_keyframe(self) -> None:
    if self._stand_key_id >= 0:
      mujoco.mj_resetDataKeyframe(self.model, self.data, self._stand_key_id)
    else:
      mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)

  def reset(self):
    self._apply_stand_keyframe()
    if self.viewer is not None:
      self.viewer.sync()

    imu_x = float(self.data.site("imu_site").xpos[0])
    imu_z = float(self.data.site("imu_site").xpos[2])
    left_foot_x = float(self.data.site(LEFT_FOOT_SITE).xpos[0])
    right_foot_x = float(self.data.site(RIGHT_FOOT_SITE).xpos[0])
    self._episode.reset_forward_tracking(
      imu_x=imu_x,
      left_foot_x=left_foot_x,
      right_foot_x=right_foot_x,
      imu_z=imu_z,
      n_action=config.ACTION_DIM,
    )

    policy_obs, _ = self._observation.build(
      self.model, self.data, self._episode, dx=0.0
    )
    return policy_obs.to_vector()

  def step(self, action, visualize: bool = False, episode_step: int = 0):
    _ = episode_step
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
    left_foot_x = float(self.data.site(LEFT_FOOT_SITE).xpos[0])
    right_foot_x = float(self.data.site(RIGHT_FOOT_SITE).xpos[0])
    dx = imu_x - self._episode.prev_imu_x
    left_foot_dx = left_foot_x - self._episode.prev_left_foot_x
    right_foot_dx = right_foot_x - self._episode.prev_right_foot_x

    policy_obs, step_physics = self._observation.build(
      self.model,
      self.data,
      self._episode,
      dx=dx,
      left_foot_dx=left_foot_dx,
      right_foot_dx=right_foot_dx,
    )

    biped = self._episode.advance_biped_context(
      left_on_floor=step_physics.left_foot_on_floor,
      right_on_floor=step_physics.right_foot_on_floor,
      imu_z=imu_z,
    )
    progress_m = self._episode.advance_progress(
      imu_x, upright=step_physics.upright
    )

    reward_result = self._reward.compute(
      self.data,
      self._episode,
      biped=biped,
      effort=effort,
      progress_m=progress_m,
    )
    reward_breakdown = reward_result.breakdown

    self._episode.advance_imu_x(imu_x)
    self._episode.advance_foot_dx(left_foot_x, right_foot_x)

    if not termination.terminated:
      termination = self._termination.done_reason_pose(
        self.data
      )

    terminated = termination.terminated
    termination_reason = termination.reason

    reward = (
      reward_result.total
      + termination.penalty
      + shank_penalty_sum
    )

    self._episode.prev_action = prev_action

    contact_force_n = termination.contact_normal_force_n
    step_info = {
      "imu_x": imu_x,
      "imu_dx": dx,
      "upright": step_physics.upright,
      "foot_on_floor": float(step_physics.any_foot_on_floor),
      "left_foot_on_floor": float(step_physics.left_foot_on_floor),
      "right_foot_on_floor": float(step_physics.right_foot_on_floor),
      "both_feet_on_floor": float(biped.both_feet_on_floor),
      "flight_steps": float(biped.aerial_steps),
      "aerial_steps": float(biped.aerial_steps),
      "landed": float(biped.left_landed or biped.right_landed),
      "reward_forward": reward_result.forward,
      "reward_forward_imu": reward_breakdown.forward_imu,
      "reward_forward_foot": reward_breakdown.forward_foot,
      "reward_shaping": reward_result.shaping,
      "reward_upright": reward_breakdown.upright_bonus,
      "reward_push_off": reward_breakdown.push_off_bonus,
      "reward_landing": reward_breakdown.landing_bonus,
      "reward_backward_lean_penalty": reward_breakdown.backward_lean_penalty,
      "reward_forward_lean_penalty": reward_breakdown.forward_lean_penalty,
      "reward_height_penalty": reward_breakdown.height_penalty,
      "reward_flight_duration_penalty": reward_breakdown.flight_duration_penalty,
      "reward_progress": reward_breakdown.progress_bonus,
      "reward_knee_hyperflex_penalty": reward_breakdown.knee_hyperflex_penalty,
      "foot_dx": step_physics.foot_dx,
      "left_foot_dx": step_physics.left_foot_dx,
      "right_foot_dx": step_physics.right_foot_dx,
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


# 後方互換（import 名）
Env2JointPPO = EnvBipedPPO
