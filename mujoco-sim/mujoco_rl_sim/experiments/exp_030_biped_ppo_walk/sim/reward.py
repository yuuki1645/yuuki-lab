"""両脚交互片脚歩行 PPO 向けステップ報酬（exp_026 ホップ主線から分岐）。"""

from dataclasses import dataclass

import mujoco
import numpy as np

from lib.experiment_context import ExperimentContext
from sim.effort import EffortBreakdown
from sim.episode_state import BipedStepContext, EpisodeState
from lib.actuators import (
  LEFT_FOOT_GEOM,
  LEFT_FOOT_SITE,
  RIGHT_FOOT_GEOM,
  RIGHT_FOOT_SITE,
)
from lib.pose import pose_metrics
from sim.observation import (
  LEFT_HEEL_SITE,
  LEFT_TOE_SITE,
  RIGHT_HEEL_SITE,
  RIGHT_TOE_SITE,
  StepPhysics,
)

WORLD_X = 0
WORLD_Z = 2


@dataclass(frozen=True)
class RewardBreakdown:
  forward_imu: float
  forward_foot: float
  upright_bonus: float
  push_off_bonus: float
  landing_bonus: float
  alternating_landing_bonus: float
  swing_clearance_bonus: float
  backward_lean_penalty: float
  forward_lean_penalty: float
  height_penalty: float
  flight_duration_penalty: float
  progress_bonus: float
  knee_hyperflex_penalty: float
  heading_misalign_penalty: float
  lateral_tilt_penalty: float
  double_support_penalty: float
  effort_penalty: float
  effort_power_cost: float


@dataclass(frozen=True)
class RewardResult:
  total: float
  forward: float
  shaping: float
  breakdown: RewardBreakdown


class Reward:
  def __init__(self, model: mujoco.MjModel, ctx: ExperimentContext):
    self._ctx = ctx
    self._imu_site_id = model.site("imu_site").id
    self._left_foot_site_id = model.site(LEFT_FOOT_SITE).id
    self._right_foot_site_id = model.site(RIGHT_FOOT_SITE).id
    self._floor_geom_id = model.geom("floor").id
    self._left_foot_geom_id = model.geom(LEFT_FOOT_GEOM).id
    self._right_foot_geom_id = model.geom(RIGHT_FOOT_GEOM).id
    self._left_knee_joint_id = model.joint("left_knee_pitch").id
    self._right_knee_joint_id = model.joint("right_knee_pitch").id

  def _geom_on_floor(self, data: mujoco.MjData, geom_id: int) -> bool:
    for i in range(data.ncon):
      c = data.contact[i]
      if (c.geom1 == geom_id and c.geom2 == self._floor_geom_id) or (
        c.geom2 == geom_id and c.geom1 == self._floor_geom_id
      ):
        return True
    return False

  def _aerial_duration_penalty(self, *, any_foot_on_floor: bool, aerial_steps: int) -> float:
    """両足非接地が AERIAL_DURATION_PENALTY_AFTER_STEPS を超えるとホップ抑制ペナルティ。"""
    if any_foot_on_floor:
      return 0.0
    over = aerial_steps - self._ctx.cfg.reward.aerial_duration_penalty_after_steps
    if over <= 0:
      return 0.0
    return over * self._ctx.cfg.reward.aerial_duration_penalty_scale

  def _progress_bonus(self, progress_m: float) -> float:
    """エピソード内で IMU +X が過去最高を更新した分だけボーナス（片足支持時のみ加算）。"""
    return float(progress_m) * self._ctx.cfg.reward.progress_reward_scale

  def _knee_hyperflex_penalty(
    self,
    left_knee_angle: float,
    right_knee_angle: float,
    *,
    any_foot_on_floor: bool,
  ) -> float:
    if self._ctx.cfg.reward.knee_hyperflex_aerial_only and any_foot_on_floor:
      return 0.0
    knee = max(left_knee_angle, right_knee_angle)
    excess = float(
      np.clip(float(knee) - self._ctx.cfg.reward.knee_hyperflex_max_rad, 0.0, np.inf)
    )
    return excess * self._ctx.cfg.reward.knee_hyperflex_penalty_scale

  def _upright_bonus(self, upright: float, *, dx: float) -> float:
    if dx < self._ctx.cfg.reward.upright_bonus_min_dx:
      return 0.0
    return (
      float(np.clip(float(upright) - self._ctx.cfg.reward.upright_bonus_thresh, 0.0, np.inf))
      * self._ctx.cfg.reward.upright_bonus_scale
    )

  def _backward_lean_penalty(self, lean_fwd_body: float) -> float:
    excess = float(
      np.clip(-float(lean_fwd_body) - self._ctx.cfg.reward.lean_backward_thresh, 0.0, np.inf)
    )
    return excess * self._ctx.cfg.reward.lean_backward_penalty_scale

  def _forward_lean_penalty(
    self, lean_fwd_body: float, *, any_foot_on_floor: bool, aerial_steps: int
  ) -> float:
    if any_foot_on_floor:
      return 0.0
    if aerial_steps < self._ctx.cfg.reward.lean_forward_min_aerial_steps:
      return 0.0
    excess = float(
      np.clip(float(lean_fwd_body) - self._ctx.cfg.reward.lean_forward_thresh, 0.0, np.inf)
    )
    return excess * self._ctx.cfg.reward.lean_forward_penalty_scale

  def _heading_misalign_penalty(self, heading_align: float) -> float:
    excess = float(
      np.clip(self._ctx.cfg.reward.heading_align_min - float(heading_align), 0.0, np.inf)
    )
    return excess * self._ctx.cfg.reward.heading_misalign_penalty_scale

  def _lateral_tilt_penalty(self, tilt_horiz: float) -> float:
    excess = float(
      np.clip(float(tilt_horiz) - self._ctx.cfg.reward.lateral_tilt_thresh, 0.0, np.inf)
    )
    return excess * self._ctx.cfg.reward.lateral_tilt_penalty_scale

  def _height_penalty(
    self,
    imu_z: float,
    *,
    single_support: bool,
    both_feet_on_floor: bool,
    any_foot_on_floor: bool,
  ) -> float:
    if not any_foot_on_floor:
      if float(imu_z) < self._ctx.cfg.reward.height_penalty_aerial_crash_z:
        deficit = float(np.clip(self._ctx.cfg.reward.target_imu_z - float(imu_z), 0.0, np.inf))
        return deficit * self._ctx.cfg.reward.imu_height_penalty_scale * 1.5
      deficit = float(np.clip(self._ctx.cfg.reward.target_imu_z - float(imu_z), 0.0, np.inf))
      return deficit * self._ctx.cfg.reward.imu_height_penalty_scale
    if single_support:
      target = self._ctx.cfg.reward.target_imu_z_single_stance
    elif both_feet_on_floor:
      target = self._ctx.cfg.reward.target_imu_z_double_stance
    else:
      target = self._ctx.cfg.reward.target_imu_z
    deficit = float(np.clip(target - float(imu_z), 0.0, np.inf))
    return deficit * self._ctx.cfg.reward.imu_height_penalty_scale

  def _double_support_penalty(
    self,
    *,
    both_feet_on_floor: bool,
    dx: float,
    left_foot_dx: float,
    right_foot_dx: float,
  ) -> float:
    """両足接地中の前進（すり足）を抑制。前進量に比例してペナルティ。"""
    if not both_feet_on_floor:
      return 0.0
    forward_motion = max(
      float(np.clip(dx, 0.0, np.inf)),
      float(np.clip(left_foot_dx, 0.0, np.inf)),
      float(np.clip(right_foot_dx, 0.0, np.inf)),
    )
    if forward_motion < self._ctx.cfg.reward.double_support_min_forward:
      return self._ctx.cfg.reward.double_support_penalty_scale * 0.25
    return forward_motion * self._ctx.cfg.reward.double_support_penalty_scale

  def _swing_clearance_bonus(
    self,
    *,
    single_support: bool,
    single_support_side: int,
    left_foot_on_floor: bool,
    right_foot_on_floor: bool,
    left_foot_z: float,
    right_foot_z: float,
  ) -> float:
    """遊脚が SWING_MIN_FOOT_Z 以上持ち上がっているとボーナス（つまずき防止）。"""
    if not single_support:
      return 0.0
    if single_support_side == 1 and not right_foot_on_floor:
      clearance = float(right_foot_z) - self._ctx.cfg.reward.swing_min_foot_z
    elif single_support_side == -1 and not left_foot_on_floor:
      clearance = float(left_foot_z) - self._ctx.cfg.reward.swing_min_foot_z
    else:
      return 0.0
    return (
      float(np.clip(clearance, 0.0, np.inf)) * self._ctx.cfg.reward.swing_clearance_bonus_scale
    )

  def _push_off_bonus(
    self,
    physics: StepPhysics,
    *,
    biped: BipedStepContext,
    imu_dz: float,
  ) -> float:
    """支持脚の押し出し: 片足支持中に足が前へ動き、膝伸展 or IMU 上昇。"""
    if not biped.single_support:
      return 0.0
    if biped.single_support_side == 1:
      foot_dx = physics.left_foot_dx
      knee_vel = physics.left_knee_vel
    else:
      foot_dx = physics.right_foot_dx
      knee_vel = physics.right_knee_vel
    if foot_dx < self._ctx.cfg.reward.push_off_min_foot_dx:
      return 0.0
    extending = knee_vel < -self._ctx.cfg.reward.push_off_min_knee_ext_vel
    rising = imu_dz >= self._ctx.cfg.reward.push_off_min_imu_dz
    if not (extending or rising):
      return 0.0
    return self._ctx.cfg.reward.push_off_bonus_scale

  def _landing_bonus(
    self,
    physics: StepPhysics,
    *,
    biped: BipedStepContext,
  ) -> float:
    """着地ステップ: つま先・かかとが低く、前傾しすぎない着地にボーナス。"""
    if biped.left_landed:
      toe_z = physics.left_toe_z
      heel_z = physics.left_heel_z
    elif biped.right_landed:
      toe_z = physics.right_toe_z
      heel_z = physics.right_heel_z
    else:
      return 0.0
    if toe_z > self._ctx.cfg.reward.landing_max_toe_z:
      return 0.0
    if heel_z > self._ctx.cfg.reward.landing_max_heel_z:
      return 0.0
    if physics.lean_fwd_body > self._ctx.cfg.reward.landing_max_forward_lean:
      return 0.0
    return self._ctx.cfg.reward.landing_bonus_scale

  def _alternating_landing_bonus(self, *, biped: BipedStepContext) -> float:
    """反対脚支持からの着地（左右交互）を検出したステップにボーナス。"""
    if not biped.alternating_landing:
      return 0.0
    return self._ctx.cfg.reward.alternating_landing_bonus_scale

  def compute(
    self,
    data: mujoco.MjData,
    episode: EpisodeState,
    *,
    biped: BipedStepContext,
    effort: EffortBreakdown,
    physics: StepPhysics,
    progress_m: float = 0.0,
  ) -> RewardResult:
    # 報酬合成: forward = IMU/支持脚前進, shaping = 歩行 shaping ± ペナルティ

    max_dx_per_step = self._ctx.cfg.sim.max_dx_per_step

    #region 生値読み出し（位置・速度差分）
    imu_x = float(data.site_xpos[self._imu_site_id, WORLD_X])
    imu_z = float(data.site_xpos[self._imu_site_id, WORLD_Z])
    left_foot_x = float(data.site_xpos[self._left_foot_site_id, WORLD_X])
    right_foot_x = float(data.site_xpos[self._right_foot_site_id, WORLD_X])
    dx = imu_x - episode.prev_imu_x
    left_foot_dx = left_foot_x - episode.prev_left_foot_x
    right_foot_dx = right_foot_x - episode.prev_right_foot_x
    #endregion

    #region 接地・姿勢
    left_foot_on_floor = self._geom_on_floor(data, self._left_foot_geom_id)
    right_foot_on_floor = self._geom_on_floor(data, self._right_foot_geom_id)
    any_foot_on_floor = left_foot_on_floor or right_foot_on_floor
    single_support = biped.single_support

    imu_zaxis = data.sensor("imu_zaxis").data
    upright = float(imu_zaxis[WORLD_Z])
    lean_fwd_body, heading_align, tilt_horiz = pose_metrics(imu_zaxis, data)

    left_knee_angle = float(data.joint(self._left_knee_joint_id).qpos[0])
    right_knee_angle = float(data.joint(self._right_knee_joint_id).qpos[0])

    step_physics = physics
    imu_dz = episode.imu_dz(imu_z)
    #endregion

    #region 前進ゲート（片足支持・直立・接地）
    forward_allowed = upright >= self._ctx.cfg.reward.forward_min_upright
    if self._ctx.cfg.reward.forward_require_foot_contact and not any_foot_on_floor:
      forward_allowed = False
    if self._ctx.cfg.reward.forward_require_single_support and not single_support:
      forward_allowed = False

    imu_forward_scale = 1.0
    if (
      self._ctx.cfg.reward.forward_imu_lean_gate
      and not any_foot_on_floor
      and forward_allowed
    ):
      lean_excess = float(
        np.clip(lean_fwd_body - self._ctx.cfg.reward.forward_imu_lean_gate_thresh, 0.0, np.inf)
      )
      imu_forward_scale = float(
        np.clip(
          1.0 - self._ctx.cfg.reward.forward_imu_lean_gate_scale * lean_excess,
          self._ctx.cfg.reward.forward_imu_lean_gate_min_mult,
          np.inf,
        )
      )
    #endregion

    #region 前進報酬 forward_imu / forward_foot
    dx_clipped = float(np.clip(dx, -max_dx_per_step, max_dx_per_step))
    forward_imu = 0.0
    if forward_allowed:
      forward_imu = (
        float(np.clip(dx_clipped, 0.0, np.inf))
        * self._ctx.cfg.reward.forward_reward_scale
        * imu_forward_scale
      )

    stance_foot_dx = 0.0
    # 支持脚（single_support_side）の +X 移動のみ forward_foot に反映
    if single_support and biped.single_support_side == 1:
      stance_foot_dx = float(np.clip(left_foot_dx, 0.0, np.inf))
    elif single_support and biped.single_support_side == -1:
      stance_foot_dx = float(np.clip(right_foot_dx, 0.0, np.inf))
    foot_dx_clipped = float(np.clip(stance_foot_dx, -max_dx_per_step, max_dx_per_step))
    forward_foot = 0.0
    if forward_allowed:
      forward_foot = foot_dx_clipped * self._ctx.cfg.reward.forward_reward_scale
    #endregion

    #region effort
    effort_penalty = effort.penalty if self._ctx.cfg.reward.enable_effort else 0.0
    #endregion

    #region shaping — 歩行ボーナス
    upright_bonus = self._upright_bonus(upright, dx=dx)
    push_off_bonus = self._push_off_bonus(step_physics, biped=biped, imu_dz=imu_dz)
    landing_bonus = self._landing_bonus(step_physics, biped=biped)
    alternating_landing_bonus = self._alternating_landing_bonus(biped=biped)
    swing_clearance_bonus = self._swing_clearance_bonus(
      single_support=single_support,
      single_support_side=biped.single_support_side,
      left_foot_on_floor=left_foot_on_floor,
      right_foot_on_floor=right_foot_on_floor,
      left_foot_z=step_physics.left_foot_z,
      right_foot_z=step_physics.right_foot_z,
    )
    progress_bonus = self._progress_bonus(progress_m)
    #endregion

    #region shaping — 姿勢・すり足・ホップ抑制ペナルティ
    backward_lean_penalty = self._backward_lean_penalty(lean_fwd_body)
    forward_lean_penalty = self._forward_lean_penalty(
      lean_fwd_body,
      any_foot_on_floor=any_foot_on_floor,
      aerial_steps=biped.aerial_steps,
    )
    heading_misalign_penalty = self._heading_misalign_penalty(heading_align)
    lateral_tilt_penalty = self._lateral_tilt_penalty(tilt_horiz)
    height_penalty = self._height_penalty(
      imu_z,
      single_support=single_support,
      both_feet_on_floor=biped.both_feet_on_floor,
      any_foot_on_floor=any_foot_on_floor,
    )
    flight_duration_penalty = self._aerial_duration_penalty(
      any_foot_on_floor=any_foot_on_floor, aerial_steps=biped.aerial_steps
    )
    knee_hyperflex_penalty = self._knee_hyperflex_penalty(
      left_knee_angle,
      right_knee_angle,
      any_foot_on_floor=any_foot_on_floor,
    )
    double_support_penalty = self._double_support_penalty(
      both_feet_on_floor=biped.both_feet_on_floor,
      dx=dx,
      left_foot_dx=left_foot_dx,
      right_foot_dx=right_foot_dx,
    )
    #endregion

    #region ENABLE 群による項の無効化（config.REWARD_ENABLE_*）
    if not self._ctx.cfg.reward.enable_forward:
      forward_imu = 0.0
    if not self._ctx.cfg.reward.enable_forward_foot:
      forward_foot = 0.0
    if not self._ctx.cfg.reward.enable_progress:
      progress_bonus = 0.0
    if not self._ctx.cfg.reward.enable_walk_shaping:
      push_off_bonus = 0.0
      landing_bonus = 0.0
      alternating_landing_bonus = 0.0
      swing_clearance_bonus = 0.0
    if not self._ctx.cfg.reward.enable_upright_bonus:
      upright_bonus = 0.0
    if not self._ctx.cfg.reward.enable_posture_penalties:
      backward_lean_penalty = 0.0
      forward_lean_penalty = 0.0
      heading_misalign_penalty = 0.0
      lateral_tilt_penalty = 0.0
      height_penalty = 0.0
      knee_hyperflex_penalty = 0.0
    if not self._ctx.cfg.reward.enable_double_support:
      double_support_penalty = 0.0
    if not self._ctx.cfg.reward.enable_flight_duration:
      flight_duration_penalty = 0.0
    #endregion

    #region breakdown 組み立て
    breakdown = RewardBreakdown(
      forward_imu=forward_imu,
      forward_foot=forward_foot,
      upright_bonus=upright_bonus,
      push_off_bonus=push_off_bonus,
      landing_bonus=landing_bonus,
      alternating_landing_bonus=alternating_landing_bonus,
      swing_clearance_bonus=swing_clearance_bonus,
      backward_lean_penalty=backward_lean_penalty,
      forward_lean_penalty=forward_lean_penalty,
      height_penalty=height_penalty,
      flight_duration_penalty=flight_duration_penalty,
      progress_bonus=progress_bonus,
      knee_hyperflex_penalty=knee_hyperflex_penalty,
      heading_misalign_penalty=heading_misalign_penalty,
      lateral_tilt_penalty=lateral_tilt_penalty,
      double_support_penalty=double_support_penalty,
      effort_penalty=effort_penalty,
      effort_power_cost=effort.power_cost,
    )
    #endregion

    #region 合成 total / forward / shaping
    forward = forward_imu + forward_foot
    shaping = (
      upright_bonus
      + push_off_bonus
      + landing_bonus
      + alternating_landing_bonus
      + swing_clearance_bonus
      + progress_bonus
      - backward_lean_penalty
      - forward_lean_penalty
      - height_penalty
      - flight_duration_penalty
      - knee_hyperflex_penalty
      - heading_misalign_penalty
      - lateral_tilt_penalty
      - double_support_penalty
    )
    total = forward + shaping - effort_penalty
    #endregion

    return RewardResult(
      total=total,
      forward=forward,
      shaping=shaping,
      breakdown=breakdown,
    )
