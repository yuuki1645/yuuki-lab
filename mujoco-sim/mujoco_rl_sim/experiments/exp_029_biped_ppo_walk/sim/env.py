"""exp_029: 両脚交互片脚歩行 PPO（ボディフレーム姿勢・12 DOF）。"""

from __future__ import annotations

import time
import mujoco
import numpy as np
import mujoco.viewer
from mujoco_sim_common.viewer_height_overlay import sync_viewer_with_height_overlay
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

from lib.experiment_context import ExperimentContext, build_experiment_context
from lib.hydra_checkpoint import load_cfg_from_yaml
from conf.schema import build_app_config
from sim.episode_state import EpisodeState
from telemetry.biped_ppo import (
  actuator_names,
  joint_qpos_to_logical_deg,
  policy_action_to_logical_deg,
)

from lib.action import ActionBinding
from lib.actuators import LEFT_FOOT_SITE, RIGHT_FOOT_SITE
from sim.observation import Observation
from sim.effort import EffortTracker
from sim.reward import Reward
from sim.domain_randomization import (
  TrainingDomainRandomization,
  make_episode_dr_rng,
)
from sim.termination import (
  NOT_TERMINATED,
  REASON_CONTACT_BASKET,
  REASON_CONTACT_THIGH,
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_BACKWARD_LEAN,
  Termination,
)

class EnvBipedPPO:
  """両脚 12 DOF・観測 51 次元・+X 交互片脚歩行タスク。

  1 制御ステップ = FRAME_SKIP 回の mj_step → 観測・報酬・終了判定。
  報酬の詳細は sim/reward.py、歩行位相は sim/episode_state.py を参照。
  """

  def __init__(
    self,
    ctx: ExperimentContext | None = None,
    *,
    enable_viewer: bool = True,
    training_dr_enabled: bool | None = None,
    training_seed: int | None = None,
    hydra_config_path: str | None = None,
  ):
    if ctx is None:
      if hydra_config_path is None:
        # 既存の単体利用（scripts/tests）向けに default AppConfig から組み立てる。
        ctx = build_experiment_context(build_app_config())
      else:
        # subprocess 側では YAML だけを受け取り、この場で Context を再構築する。
        loaded_cfg = load_cfg_from_yaml(hydra_config_path)
        ctx = build_experiment_context(loaded_cfg)
    self._ctx = ctx

    self.model = mujoco.MjModel.from_xml_path(self._ctx.xml_path)
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)

    if training_dr_enabled is None:
      training_dr_enabled = bool(self._ctx.cfg.training.training_dr)
    self._training_dr_enabled = bool(training_dr_enabled)
    self._training_seed = training_seed
    self._training_dr = TrainingDomainRandomization(self.model, self._ctx)

    physics_dt = float(self.model.opt.timestep)
    if abs(physics_dt - self._ctx.cfg.sim.physics_timestep_s) > 1e-9:
      raise ValueError(
        f"model.opt.timestep={physics_dt} != cfg.sim.physics_timestep_s={self._ctx.cfg.sim.physics_timestep_s}"
      )

    self.viewer = None
    if enable_viewer:
      self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
      apply_passive_viewer_options(self.viewer)

    self._episode = EpisodeState(ctx=self._ctx)
    self._action = ActionBinding(self.model)
    self._observation = Observation(self.model, self._ctx)
    self._reward = Reward(self.model, self._ctx)
    self._effort = EffortTracker(self.model, self._ctx)
    self._termination = Termination(self.model, self._ctx)
    self._stand_key_id = mujoco.mj_name2id(
      self.model, mujoco.mjtObj.mjOBJ_KEY, "stand"
    )
    self._step_wall_sleep_sec = float(self._ctx.cfg.runtime.step_wall_sleep_sec)

  def _apply_stand_keyframe(self) -> None:
    if self._stand_key_id >= 0:
      mujoco.mj_resetDataKeyframe(self.model, self.data, self._stand_key_id)
    else:
      mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)

  def _finalize_reset(self) -> tuple[np.ndarray, float]:
    """物理状態確定後にエピソード状態・観測を初期化する。

    Returns:
      (obs_vector, origin_imu_x) … origin はノイズ適用後の IMU 世界 X [m]。
    """
    if self.viewer is not None:
      sync_viewer_with_height_overlay(self.viewer, self._ctx)

    imu_x = float(self.data.site("imu_site").xpos[0])
    imu_z = float(self.data.site("imu_site").xpos[2])
    left_foot_x = float(self.data.site(LEFT_FOOT_SITE).xpos[0])
    right_foot_x = float(self.data.site(RIGHT_FOOT_SITE).xpos[0])
    self._episode.reset_forward_tracking(
      imu_x=imu_x,
      left_foot_x=left_foot_x,
      right_foot_x=right_foot_x,
      imu_z=imu_z,
      n_action=self._ctx.cfg.sim.action_dim,
    )

    policy_obs, _ = self._observation.build(
      self.model, self.data, self._episode, dx=0.0
    )
    return policy_obs.to_vector(), imu_x

  def reset(self, *, episode_index: int = 0):
    """keyframe ``stand`` から再開し、エピソード状態・観測を初期化する。

    学習 DR 有効時はエピソードごとに初期姿勢・足底摩擦・kp/kv をサンプルする。
    """
    self._training_dr.restore_nominal(self.model)
    self._apply_stand_keyframe()
    if self._training_dr_enabled:
      dr_rng = make_episode_dr_rng(self._training_seed, episode_index)
      _applied = self._training_dr.apply_for_episode(
        self.model,
        self.data,
        rng=dr_rng,
      )
    obs, _origin_imu_x = self._finalize_reset()
    return obs

  def reset_eval(self, rng: np.random.Generator) -> tuple[np.ndarray, float, dict]:
    """Eval 用 reset: stand keyframe + 初期姿勢ノイズ（学習 DR は使わない）。

    Returns:
      (obs, origin_imu_x, noise_applied)
    """
    from eval.noise import apply_initial_pose_noise

    self._training_dr.restore_nominal(self.model)
    self._apply_stand_keyframe()
    noise_applied = apply_initial_pose_noise(self.model, self.data, rng)
    obs, origin_imu_x = self._finalize_reset()
    return obs, origin_imu_x, noise_applied

  def step(self, action, visualize: bool = False, episode_step: int = 0):
    """ポリシー行動を適用し、1 制御ステップ分シミュレーションする。

    処理順:
      1. action → ctrl（ActionBinding）
      2. FRAME_SKIP 回 mj_step（接触終了・すね床接触ペナルティを毎物理ステップ評価）
      3. 観測ベクトル構築（observation.py）
      4. 歩行位相更新 → 報酬（reward.py）→ 姿勢終了（termination.py）
    """
    _ = episode_step
    prev_action = self._action.apply(self.data, action)

    termination = NOT_TERMINATED
    shank_penalty_sum = 0.0
    self._effort.reset_control_step()

    # --- 物理積分（50 Hz 制御 = 10 × 500 Hz 物理）---
    for _ in range(self._ctx.cfg.sim.frame_skip):
      mujoco.mj_step(self.model, self.data)
      self._effort.record_physics_step(self.data)
      
      termination = self._termination.done_reason_contact(self.data)
      if termination.terminated:
        break

      shank_penalty_sum += self._termination.shank_contact_step_penalty(self.data)

    effort = self._effort.control_step_breakdown()

    if self.viewer is not None:
      sync_viewer_with_height_overlay(self.viewer, self._ctx)
    if visualize:
      time.sleep(self._ctx.cfg.sim.control_timestep_s)
    elif self._step_wall_sleep_sec > 0.0:
      time.sleep(self._step_wall_sleep_sec)

    imu_x = float(self.data.site("imu_site").xpos[0])
    imu_z = float(self.data.site("imu_site").xpos[2])
    left_foot_x = float(self.data.site(LEFT_FOOT_SITE).xpos[0])
    right_foot_x = float(self.data.site(RIGHT_FOOT_SITE).xpos[0])
    dx = imu_x - self._episode.prev_imu_x
    left_foot_dx = left_foot_x - self._episode.prev_left_foot_x
    right_foot_dx = right_foot_x - self._episode.prev_right_foot_x

    # --- 観測・歩行位相・報酬 ---
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
      imu_x,
      upright=step_physics.upright,
      single_support=biped.single_support,
    )

    reward_result = self._reward.compute(
      self.data,
      self._episode,
      biped=biped,
      effort=effort,
      physics=step_physics,
      progress_m=progress_m,
    )
    reward_breakdown = reward_result.breakdown

    self._episode.advance_imu_x(imu_x)
    self._episode.advance_foot_dx(left_foot_x, right_foot_x)

    # 接触以外の転倒条件（低姿勢・後傾など）は物理ステップ後に 1 回だけ評価
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
      "single_support": float(biped.single_support),
      "single_support_side": float(biped.single_support_side),
      "alternating_landing": float(biped.alternating_landing),
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
      "reward_alternating_landing": reward_breakdown.alternating_landing_bonus,
      "reward_swing_clearance": reward_breakdown.swing_clearance_bonus,
      "reward_double_support_penalty": reward_breakdown.double_support_penalty,
      "reward_backward_lean_penalty": reward_breakdown.backward_lean_penalty,
      "reward_forward_lean_penalty": reward_breakdown.forward_lean_penalty,
      "reward_height_penalty": reward_breakdown.height_penalty,
      "reward_flight_duration_penalty": reward_breakdown.flight_duration_penalty,
      "reward_progress": reward_breakdown.progress_bonus,
      "reward_knee_hyperflex_penalty": reward_breakdown.knee_hyperflex_penalty,
      "reward_heading_misalign_penalty": reward_breakdown.heading_misalign_penalty,
      "reward_lateral_tilt_penalty": reward_breakdown.lateral_tilt_penalty,
      "lean_fwd_body": step_physics.lean_fwd_body,
      "heading_align": step_physics.heading_align,
      "tilt_horiz": step_physics.tilt_horiz,
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
      "actuator_names": actuator_names(),
      "action_logical_deg": policy_action_to_logical_deg(
        self.model, self.data, prev_action
      ),
      "joint_q_logical_deg": joint_qpos_to_logical_deg(self.model, self.data),
      "obs_imu_gyro": [
        step_physics.imu_gyro_x,
        step_physics.imu_gyro_y,
        step_physics.imu_gyro_z,
      ],
      "obs_imu_zaxis": [
        step_physics.imu_zaxis_x,
        step_physics.imu_zaxis_y,
        step_physics.imu_zaxis_z,
      ],
      "reward_total": reward,
      "reward_effort_penalty": reward_breakdown.effort_penalty,
      "torso_height": imu_z,
      "step_wall_sleep_sec": self._step_wall_sleep_sec,
      "is_fallen": terminated,
      "terminated": terminated,
      "truncated": False,
    }

    return policy_obs.to_vector(), reward, terminated, step_info

  def set_step_wall_sleep_sec(self, sec: float) -> None:
    self._step_wall_sleep_sec = max(0.0, float(sec))

  def get_step_wall_sleep_sec(self) -> float:
    return float(self._step_wall_sleep_sec)
