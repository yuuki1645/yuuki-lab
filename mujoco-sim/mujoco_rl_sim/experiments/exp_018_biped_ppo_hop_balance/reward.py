"""両脚前進 PPO 向けステップ報酬。"""

from dataclasses import dataclass

import mujoco

from . import config
from .effort import EffortBreakdown
from .episode_state import BipedStepContext, EpisodeState
from .lib.actuators import (
  LEFT_FOOT_GEOM,
  LEFT_FOOT_SITE,
  RIGHT_FOOT_GEOM,
  RIGHT_FOOT_SITE,
)


@dataclass(frozen=True)
class RewardPhysicsSnapshot:
  """報酬計算に使う 1 ステップ分の物理量。

  dx / left_foot_dx / right_foot_dx は episode の prev_* との差分（advance 前）。
  """

  dx: float
  left_foot_dx: float
  right_foot_dx: float
  imu_z: float
  upright: float
  imu_zaxis_x: float
  left_foot_on_floor: bool
  right_foot_on_floor: bool
  any_foot_on_floor: bool
  left_knee_angle: float
  right_knee_angle: float


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

  @property
  def forward(self) -> float:
    return self.forward_imu + self.forward_foot

  @property
  def shaping(self) -> float:
    return (
      self.upright_bonus
      + self.push_off_bonus
      + self.landing_bonus
      + self.progress_bonus
      - self.backward_lean_penalty
      - self.forward_lean_penalty
      - self.height_penalty
      - self.flight_duration_penalty
      - self.knee_hyperflex_penalty
    )

  @property
  def total(self) -> float:
    return self.forward + self.shaping - self.effort_penalty


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

  def _build_snapshot(
    self, data: mujoco.MjData, episode: EpisodeState
  ) -> RewardPhysicsSnapshot:
    imu_x = float(data.site_xpos[self._imu_site_id, 0])
    left_foot_x = float(data.site_xpos[self._left_foot_site_id, 0])
    right_foot_x = float(data.site_xpos[self._right_foot_site_id, 0])
    imu_z = float(data.site_xpos[self._imu_site_id, 2])

    dx = imu_x - episode.prev_imu_x
    left_foot_dx = left_foot_x - episode.prev_left_foot_x
    right_foot_dx = right_foot_x - episode.prev_right_foot_x

    left_on = self._geom_on_floor(data, self._left_foot_geom_id)
    right_on = self._geom_on_floor(data, self._right_foot_geom_id)

    imu_zaxis = data.sensor("imu_zaxis").data
    upright = float(imu_zaxis[2])

    return RewardPhysicsSnapshot(
      dx=dx,
      left_foot_dx=left_foot_dx,
      right_foot_dx=right_foot_dx,
      imu_z=imu_z,
      upright=upright,
      imu_zaxis_x=float(imu_zaxis[0]),
      left_foot_on_floor=left_on,
      right_foot_on_floor=right_on,
      any_foot_on_floor=left_on or right_on,
      left_knee_angle=float(data.joint(self._left_knee_joint_id).qpos[0]),
      right_knee_angle=float(data.joint(self._right_knee_joint_id).qpos[0]),
    )

  @staticmethod
  def _forward_imu_lean_multiplier(
    imu_zaxis_x: float, *, any_foot_on_floor: bool
  ) -> float:
    if not config.FORWARD_IMU_LEAN_GATE or any_foot_on_floor:
      return 1.0
    excess = max(
      0.0, float(imu_zaxis_x) - config.FORWARD_IMU_LEAN_GATE_THRESH
    )
    mult = 1.0 - config.FORWARD_IMU_LEAN_GATE_SCALE * excess
    return max(config.FORWARD_IMU_LEAN_GATE_MIN_MULT, mult)

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
  def _knee_hyperflex_penalty(phys: RewardPhysicsSnapshot) -> float:
    if config.KNEE_HYPERFLEX_AERIAL_ONLY and phys.any_foot_on_floor:
      return 0.0
    knee = max(phys.left_knee_angle, phys.right_knee_angle)
    excess = max(0.0, float(knee) - config.KNEE_HYPERFLEX_MAX_RAD)
    return excess * config.KNEE_HYPERFLEX_PENALTY_SCALE

  @staticmethod
  def _forward_component(
    dx: float,
    *,
    upright: float,
    allow_without_contact: bool,
    contact_ok: bool,
    scale: float = 1.0,
  ) -> float:
    dx_clipped = max(-config.MAX_DX_PER_STEP, min(config.MAX_DX_PER_STEP, float(dx)))
    if upright < config.FORWARD_MIN_UPRIGHT:
      return 0.0
    if config.FORWARD_REQUIRE_FOOT_CONTACT and not contact_ok:
      return 0.0
    if not allow_without_contact and not contact_ok:
      return 0.0
    return max(0.0, dx_clipped) * config.FORWARD_REWARD_SCALE * max(0.0, float(scale))

  @staticmethod
  def _forward_foot_sum(phys: RewardPhysicsSnapshot) -> float:
    total = 0.0
    if phys.left_foot_on_floor:
      total += max(0.0, phys.left_foot_dx)
    if phys.right_foot_on_floor:
      total += max(0.0, phys.right_foot_dx)
    return total

  @staticmethod
  def _upright_bonus(upright: float, *, dx: float) -> float:
    if dx < config.UPRIGHT_BONUS_MIN_DX:
      return 0.0
    return (
      max(0.0, float(upright) - config.UPRIGHT_BONUS_THRESH)
      * config.UPRIGHT_BONUS_SCALE
    )

  @staticmethod
  def _backward_lean_penalty(imu_zaxis_x: float) -> float:
    excess = max(0.0, -float(imu_zaxis_x) - config.LEAN_BACKWARD_THRESH)
    return excess * config.LEAN_BACKWARD_PENALTY_SCALE

  @staticmethod
  def _forward_lean_penalty(
    imu_zaxis_x: float, *, any_foot_on_floor: bool, aerial_steps: int
  ) -> float:
    if any_foot_on_floor:
      return 0.0
    if aerial_steps < config.LEAN_FORWARD_MIN_AERIAL_STEPS:
      return 0.0
    excess = max(0.0, float(imu_zaxis_x) - config.LEAN_FORWARD_THRESH)
    return excess * config.LEAN_FORWARD_PENALTY_SCALE

  @staticmethod
  def _height_penalty(imu_z: float, *, any_foot_on_floor: bool) -> float:
    if config.HEIGHT_PENALTY_SKIP_WHEN_STANCE and any_foot_on_floor:
      target = config.TARGET_IMU_Z_STANCE
      deficit = max(0.0, target - float(imu_z))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE
    if float(imu_z) < config.HEIGHT_PENALTY_AERIAL_CRASH_Z:
      deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE * 1.5
    deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
    return deficit * config.IMU_HEIGHT_PENALTY_SCALE

  def compute(
    self,
    data: mujoco.MjData,
    episode: EpisodeState,
    *,
    biped: BipedStepContext,
    effort: EffortBreakdown,
    progress_m: float = 0.0,
  ) -> RewardBreakdown:
    phys = self._build_snapshot(data, episode)
    upright = phys.upright
    any_foot = phys.any_foot_on_floor

    imu_forward_scale = self._forward_imu_lean_multiplier(
      phys.imu_zaxis_x, any_foot_on_floor=any_foot
    )
    forward_imu = self._forward_component(
      phys.dx,
      upright=upright,
      allow_without_contact=True,
      contact_ok=any_foot,
      scale=imu_forward_scale,
    )

    foot_dx = self._forward_foot_sum(phys)
    foot_allowed = not config.FORWARD_FOOT_ONLY_WHEN_CONTACT or any_foot
    forward_foot = self._forward_component(
      foot_dx,
      upright=upright,
      allow_without_contact=foot_allowed,
      contact_ok=any_foot,
    )

    effort_penalty = effort.penalty if config.APPLY_EFFORT_PENALTY else 0.0

    return RewardBreakdown(
      forward_imu=forward_imu,
      forward_foot=forward_foot,
      upright_bonus=self._upright_bonus(upright, dx=phys.dx),
      push_off_bonus=0.0,
      landing_bonus=0.0,
      backward_lean_penalty=self._backward_lean_penalty(phys.imu_zaxis_x),
      forward_lean_penalty=self._forward_lean_penalty(
        phys.imu_zaxis_x,
        any_foot_on_floor=any_foot,
        aerial_steps=biped.aerial_steps,
      ),
      height_penalty=self._height_penalty(
        phys.imu_z, any_foot_on_floor=any_foot
      ),
      flight_duration_penalty=self._aerial_duration_penalty(
        any_foot_on_floor=any_foot, aerial_steps=biped.aerial_steps
      ),
      progress_bonus=self._progress_bonus(progress_m),
      knee_hyperflex_penalty=self._knee_hyperflex_penalty(phys),
      effort_penalty=effort_penalty,
      effort_power_cost=effort.power_cost,
    )
