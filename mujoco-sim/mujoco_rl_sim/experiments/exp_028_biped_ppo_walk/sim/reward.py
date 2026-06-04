"""両脚交互片脚歩行 PPO 向けステップ報酬（exp_026 ホップ主線から分岐）。"""

from dataclasses import dataclass

import mujoco
import numpy as np

import config
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
  def __init__(self, model: mujoco.MjModel):
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

  @staticmethod
  def _aerial_duration_penalty(*, any_foot_on_floor: bool, aerial_steps: int) -> float:
    """両足非接地が AERIAL_DURATION_PENALTY_AFTER_STEPS を超えるとホップ抑制ペナルティ。"""
    if any_foot_on_floor:
      return 0.0
    over = aerial_steps - config.AERIAL_DURATION_PENALTY_AFTER_STEPS
    if over <= 0:
      return 0.0
    return over * config.AERIAL_DURATION_PENALTY_SCALE

  @staticmethod
  def _progress_bonus(progress_m: float) -> float:
    """エピソード内で IMU +X が過去最高を更新した分だけボーナス（片足支持時のみ加算）。"""
    return float(progress_m) * config.PROGRESS_REWARD_SCALE

  @staticmethod
  def _knee_hyperflex_penalty(
    left_knee_angle: float,
    right_knee_angle: float,
    *,
    any_foot_on_floor: bool,
  ) -> float:
    if config.KNEE_HYPERFLEX_AERIAL_ONLY and any_foot_on_floor:
      return 0.0
    knee = max(left_knee_angle, right_knee_angle)
    excess = float(np.clip(float(knee) - config.KNEE_HYPERFLEX_MAX_RAD, 0.0, np.inf))
    return excess * config.KNEE_HYPERFLEX_PENALTY_SCALE

  @staticmethod
  def _upright_bonus(upright: float, *, dx: float) -> float:
    if dx < config.UPRIGHT_BONUS_MIN_DX:
      return 0.0
    return (
      float(np.clip(float(upright) - config.UPRIGHT_BONUS_THRESH, 0.0, np.inf))
      * config.UPRIGHT_BONUS_SCALE
    )

  @staticmethod
  def _backward_lean_penalty(lean_fwd_body: float) -> float:
    excess = float(
      np.clip(-float(lean_fwd_body) - config.LEAN_BACKWARD_THRESH, 0.0, np.inf)
    )
    return excess * config.LEAN_BACKWARD_PENALTY_SCALE

  @staticmethod
  def _forward_lean_penalty(
    lean_fwd_body: float, *, any_foot_on_floor: bool, aerial_steps: int
  ) -> float:
    if any_foot_on_floor:
      return 0.0
    if aerial_steps < config.LEAN_FORWARD_MIN_AERIAL_STEPS:
      return 0.0
    excess = float(
      np.clip(float(lean_fwd_body) - config.LEAN_FORWARD_THRESH, 0.0, np.inf)
    )
    return excess * config.LEAN_FORWARD_PENALTY_SCALE

  @staticmethod
  def _heading_misalign_penalty(heading_align: float) -> float:
    excess = float(
      np.clip(config.HEADING_ALIGN_MIN - float(heading_align), 0.0, np.inf)
    )
    return excess * config.HEADING_MISALIGN_PENALTY_SCALE

  @staticmethod
  def _lateral_tilt_penalty(tilt_horiz: float) -> float:
    excess = float(
      np.clip(float(tilt_horiz) - config.LATERAL_TILT_THRESH, 0.0, np.inf)
    )
    return excess * config.LATERAL_TILT_PENALTY_SCALE

  @staticmethod
  def _height_penalty(
    imu_z: float,
    *,
    single_support: bool,
    both_feet_on_floor: bool,
    any_foot_on_floor: bool,
  ) -> float:
    if not any_foot_on_floor:
      if float(imu_z) < config.HEIGHT_PENALTY_AERIAL_CRASH_Z:
        deficit = float(np.clip(config.TARGET_IMU_Z - float(imu_z), 0.0, np.inf))
        return deficit * config.IMU_HEIGHT_PENALTY_SCALE * 1.5
      deficit = float(np.clip(config.TARGET_IMU_Z - float(imu_z), 0.0, np.inf))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE
    if single_support:
      target = config.TARGET_IMU_Z_SINGLE_STANCE
    elif both_feet_on_floor:
      target = config.TARGET_IMU_Z_DOUBLE_STANCE
    else:
      target = config.TARGET_IMU_Z
    deficit = float(np.clip(target - float(imu_z), 0.0, np.inf))
    return deficit * config.IMU_HEIGHT_PENALTY_SCALE

  @staticmethod
  def _double_support_penalty(
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
    if forward_motion < config.DOUBLE_SUPPORT_MIN_FORWARD:
      return config.DOUBLE_SUPPORT_PENALTY_SCALE * 0.25
    return forward_motion * config.DOUBLE_SUPPORT_PENALTY_SCALE

  @staticmethod
  def _swing_clearance_bonus(
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
      clearance = float(right_foot_z) - config.SWING_MIN_FOOT_Z
    elif single_support_side == -1 and not left_foot_on_floor:
      clearance = float(left_foot_z) - config.SWING_MIN_FOOT_Z
    else:
      return 0.0
    return (
      float(np.clip(clearance, 0.0, np.inf)) * config.SWING_CLEARANCE_BONUS_SCALE
    )

  @staticmethod
  def _push_off_bonus(
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
    if foot_dx < config.PUSH_OFF_MIN_FOOT_DX:
      return 0.0
    extending = knee_vel < -config.PUSH_OFF_MIN_KNEE_EXT_VEL
    rising = imu_dz >= config.PUSH_OFF_MIN_IMU_DZ
    if not (extending or rising):
      return 0.0
    return config.PUSH_OFF_BONUS_SCALE

  @staticmethod
  def _landing_bonus(
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
    if toe_z > config.LANDING_MAX_TOE_Z:
      return 0.0
    if heel_z > config.LANDING_MAX_HEEL_Z:
      return 0.0
    if physics.lean_fwd_body > config.LANDING_MAX_FORWARD_LEAN:
      return 0.0
    return config.LANDING_BONUS_SCALE

  @staticmethod
  def _alternating_landing_bonus(*, biped: BipedStepContext) -> float:
    """反対脚支持からの着地（左右交互）を検出したステップにボーナス。"""
    if not biped.alternating_landing:
      return 0.0
    return config.ALTERNATING_LANDING_BONUS_SCALE

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

    MAX_DX_PER_STEP = config.MAX_DX_PER_STEP
    APPLY_EFFORT_PENALTY = config.APPLY_EFFORT_PENALTY

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
    forward_allowed = upright >= config.FORWARD_MIN_UPRIGHT
    if config.FORWARD_REQUIRE_FOOT_CONTACT and not any_foot_on_floor:
      forward_allowed = False
    if config.FORWARD_REQUIRE_SINGLE_SUPPORT and not single_support:
      forward_allowed = False

    imu_forward_scale = 1.0
    if (
      config.FORWARD_IMU_LEAN_GATE
      and not any_foot_on_floor
      and forward_allowed
    ):
      lean_excess = float(
        np.clip(lean_fwd_body - config.FORWARD_IMU_LEAN_GATE_THRESH, 0.0, np.inf)
      )
      imu_forward_scale = float(
        np.clip(
          1.0 - config.FORWARD_IMU_LEAN_GATE_SCALE * lean_excess,
          config.FORWARD_IMU_LEAN_GATE_MIN_MULT,
          np.inf,
        )
      )
    #endregion

    #region 前進報酬 forward_imu / forward_foot
    dx_clipped = float(np.clip(dx, -MAX_DX_PER_STEP, MAX_DX_PER_STEP))
    forward_imu = 0.0
    if forward_allowed:
      forward_imu = (
        float(np.clip(dx_clipped, 0.0, np.inf))
        * config.FORWARD_REWARD_SCALE
        * imu_forward_scale
      )

    stance_foot_dx = 0.0
    # 支持脚（single_support_side）の +X 移動のみ forward_foot に反映
    if single_support and biped.single_support_side == 1:
      stance_foot_dx = float(np.clip(left_foot_dx, 0.0, np.inf))
    elif single_support and biped.single_support_side == -1:
      stance_foot_dx = float(np.clip(right_foot_dx, 0.0, np.inf))
    foot_dx_clipped = float(np.clip(stance_foot_dx, -MAX_DX_PER_STEP, MAX_DX_PER_STEP))
    forward_foot = 0.0
    if forward_allowed:
      forward_foot = foot_dx_clipped * config.FORWARD_REWARD_SCALE
    #endregion

    #region effort
    effort_penalty = effort.penalty if APPLY_EFFORT_PENALTY else 0.0
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
