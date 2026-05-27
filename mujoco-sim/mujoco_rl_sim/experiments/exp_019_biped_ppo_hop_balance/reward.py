"""両脚前進 PPO 向けステップ報酬。"""

from dataclasses import dataclass

import mujoco
import numpy as np

from . import config
from .effort import EffortBreakdown
from .episode_state import BipedStepContext, EpisodeState
from .lib.actuators import (
  LEFT_FOOT_GEOM,
  LEFT_FOOT_SITE,
  RIGHT_FOOT_GEOM,
  RIGHT_FOOT_SITE,
)

# MuJoCo site_xpos / 3D ベクトルの成分（ワールド座標: +X 前, +Y 左, +Z 上）
WORLD_X = 0
WORLD_Y = 1
WORLD_Z = 2


@dataclass(frozen=True)
class RewardBreakdown:
  forward_imu: float
  forward_foot: float
  upright_bonus: float
  push_off_bonus: float
  landing_bonus: float
  backward_lean_penalty: float
  forward_lean_penalty: float
  height_penalty: float
  flight_duration_penalty: float
  progress_bonus: float
  knee_hyperflex_penalty: float
  effort_penalty: float
  effort_power_cost: float


@dataclass(frozen=True)
class RewardResult:
  """報酬の合計と内訳。total / forward / shaping は compute 内で明示的に計算する。"""

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
    if any_foot_on_floor:
      return 0.0
    over = aerial_steps - config.AERIAL_DURATION_PENALTY_AFTER_STEPS
    if over <= 0:
      return 0.0
    return over * config.AERIAL_DURATION_PENALTY_SCALE

  @staticmethod
  def _progress_bonus(progress_m: float) -> float:
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
  def _backward_lean_penalty(imu_zaxis_x: float) -> float:
    excess = float(np.clip(-float(imu_zaxis_x) - config.LEAN_BACKWARD_THRESH, 0.0, np.inf))
    return excess * config.LEAN_BACKWARD_PENALTY_SCALE

  @staticmethod
  def _forward_lean_penalty(
    imu_zaxis_x: float, *, any_foot_on_floor: bool, aerial_steps: int
  ) -> float:
    if any_foot_on_floor:
      return 0.0
    if aerial_steps < config.LEAN_FORWARD_MIN_AERIAL_STEPS:
      return 0.0
    excess = float(np.clip(float(imu_zaxis_x) - config.LEAN_FORWARD_THRESH, 0.0, np.inf))
    return excess * config.LEAN_FORWARD_PENALTY_SCALE

  @staticmethod
  def _height_penalty(imu_z: float, *, any_foot_on_floor: bool) -> float:
    if config.HEIGHT_PENALTY_SKIP_WHEN_STANCE and any_foot_on_floor:
      target = config.TARGET_IMU_Z_STANCE
      deficit = float(np.clip(target - float(imu_z), 0.0, np.inf))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE
    if float(imu_z) < config.HEIGHT_PENALTY_AERIAL_CRASH_Z:
      deficit = float(np.clip(config.TARGET_IMU_Z - float(imu_z), 0.0, np.inf))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE * 1.5
    deficit = float(np.clip(config.TARGET_IMU_Z - float(imu_z), 0.0, np.inf))
    return deficit * config.IMU_HEIGHT_PENALTY_SCALE

  def compute(
    self,
    data: mujoco.MjData,
    episode: EpisodeState,
    *,
    biped: BipedStepContext,
    effort: EffortBreakdown,
    progress_m: float = 0.0,
  ) -> RewardResult:
    # この関数の実装は冗長だが、報酬計算の詳細について、なるべくこの関数を読むだけで
    # 理解できるように実装している。

    # NOTE(AI): この関数の実装は上記理由であえて冗長に実装している。
    # そのため、この関数内の処理については、関数などを使って簡略化・リファクタリングしないでください。

    # config（この関数内でのみ使用。hover で値を確認できるようリテラルで置く）
    # ！！！ float の定数が hover で値を確認できない・・・
    FORWARD_IMU_LEAN_GATE = True
    FORWARD_IMU_LEAN_GATE_THRESH = 0.10
    FORWARD_IMU_LEAN_GATE_SCALE = 4.0
    FORWARD_IMU_LEAN_GATE_MIN_MULT = 0.15
    MAX_DX_PER_STEP = 0.5  # 0.05 * FRAME_SKIP（FRAME_SKIP=10）
    FORWARD_MIN_UPRIGHT = 0.62
    FORWARD_REQUIRE_FOOT_CONTACT = False
    FORWARD_REWARD_SCALE = 50.0
    FORWARD_FOOT_ONLY_WHEN_CONTACT = True
    APPLY_EFFORT_PENALTY = False

    # MuJoCo: IMU / 足 site（episode.prev_* との差分は advance 前）
    imu_x = float(data.site_xpos[self._imu_site_id, WORLD_X])
    imu_z = float(data.site_xpos[self._imu_site_id, WORLD_Z])
    left_foot_x = float(data.site_xpos[self._left_foot_site_id, WORLD_X])
    right_foot_x = float(data.site_xpos[self._right_foot_site_id, WORLD_X])
    dx = imu_x - episode.prev_imu_x
    left_foot_dx = left_foot_x - episode.prev_left_foot_x
    right_foot_dx = right_foot_x - episode.prev_right_foot_x


    left_foot_on_floor = self._geom_on_floor(data, self._left_foot_geom_id)
    right_foot_on_floor = self._geom_on_floor(data, self._right_foot_geom_id)
    any_foot_on_floor = left_foot_on_floor or right_foot_on_floor

    imu_zaxis = data.sensor("imu_zaxis").data
    imu_zaxis_x = float(imu_zaxis[WORLD_X])
    upright = float(imu_zaxis[WORLD_Z])

    left_knee_angle = float(data.joint(self._left_knee_joint_id).qpos[0])
    right_knee_angle = float(data.joint(self._right_knee_joint_id).qpos[0])

    # 飛翔中の前傾が強いほど IMU 前進報酬を減衰（接地中は 1.0）
    if not FORWARD_IMU_LEAN_GATE or any_foot_on_floor:
      imu_forward_scale = 1.0
    else:
      lean_excess = float(np.clip(imu_zaxis_x - FORWARD_IMU_LEAN_GATE_THRESH, 0.0, np.inf))
      imu_forward_scale = float(
        np.clip(
          1.0 - FORWARD_IMU_LEAN_GATE_SCALE * lean_excess,
          FORWARD_IMU_LEAN_GATE_MIN_MULT,
          np.inf,
        )
      )

    # IMU の +X 移動量 dx に前進報酬（後方移動・過大 dx はクリップ）
    dx_clipped = float(np.clip(dx, -MAX_DX_PER_STEP, MAX_DX_PER_STEP))
    forward_imu = 0.0
    if upright >= FORWARD_MIN_UPRIGHT:
      if not FORWARD_REQUIRE_FOOT_CONTACT or any_foot_on_floor:
        forward_imu = (
          float(np.clip(dx_clipped, 0.0, np.inf))
          * FORWARD_REWARD_SCALE
          * float(np.clip(imu_forward_scale, 0.0, np.inf))
        )

    # 接地足の +X 移動量の合計に前進報酬
    foot_dx = 0.0
    if left_foot_on_floor:
      foot_dx += float(np.clip(left_foot_dx, 0.0, np.inf))
    if right_foot_on_floor:
      foot_dx += float(np.clip(right_foot_dx, 0.0, np.inf))
    foot_dx_clipped = float(np.clip(foot_dx, -MAX_DX_PER_STEP, MAX_DX_PER_STEP))
    foot_allowed = not FORWARD_FOOT_ONLY_WHEN_CONTACT or any_foot_on_floor
    forward_foot = 0.0
    if upright >= FORWARD_MIN_UPRIGHT:
      if not FORWARD_REQUIRE_FOOT_CONTACT or any_foot_on_floor:
        if foot_allowed or any_foot_on_floor:
          forward_foot = float(np.clip(foot_dx_clipped, 0.0, np.inf)) * FORWARD_REWARD_SCALE

    effort_penalty = effort.penalty if APPLY_EFFORT_PENALTY else 0.0

    # shaping 各項（ボーナス・ペナルティ）
    upright_bonus = self._upright_bonus(upright, dx=dx)
    push_off_bonus = 0.0
    landing_bonus = 0.0
    backward_lean_penalty = self._backward_lean_penalty(imu_zaxis_x)
    forward_lean_penalty = self._forward_lean_penalty(
      imu_zaxis_x,
      any_foot_on_floor=any_foot_on_floor,
      aerial_steps=biped.aerial_steps,
    )
    height_penalty = self._height_penalty(
      imu_z, any_foot_on_floor=any_foot_on_floor
    )
    flight_duration_penalty = self._aerial_duration_penalty(
      any_foot_on_floor=any_foot_on_floor, aerial_steps=biped.aerial_steps
    )
    progress_bonus = self._progress_bonus(progress_m)
    knee_hyperflex_penalty = self._knee_hyperflex_penalty(
      left_knee_angle,
      right_knee_angle,
      any_foot_on_floor=any_foot_on_floor,
    )

    breakdown = RewardBreakdown(
      forward_imu=forward_imu,
      forward_foot=forward_foot,
      upright_bonus=upright_bonus,
      push_off_bonus=push_off_bonus,
      landing_bonus=landing_bonus,
      backward_lean_penalty=backward_lean_penalty,
      forward_lean_penalty=forward_lean_penalty,
      height_penalty=height_penalty,
      flight_duration_penalty=flight_duration_penalty,
      progress_bonus=progress_bonus,
      knee_hyperflex_penalty=knee_hyperflex_penalty,
      effort_penalty=effort_penalty,
      effort_power_cost=effort.power_cost,
    )

    # ステップ報酬の合計（termination / shank ペナルティは env 側で加算）
    forward = forward_imu + forward_foot
    shaping = (
      upright_bonus
      + push_off_bonus
      + landing_bonus
      + progress_bonus
      - backward_lean_penalty
      - forward_lean_penalty
      - height_penalty
      - flight_duration_penalty
      - knee_hyperflex_penalty
    )
    total = forward + shaping - effort_penalty

    return RewardResult(
      total=total,
      forward=forward,
      shaping=shaping,
      breakdown=breakdown,
    )
