"""exp_008: 片脚ホッパ向けステップ報酬（exp_006 から shaping を再設計）。

1 ステップの合計（env 適用前）::

  total = forward_imu + forward_foot - effort
          + upright_flight + push_off + landing
          - backward_lean - forward_lean - height
          # 膝屈曲ボーナスなし

前進: 飛翔中の IMU dx は常時可。foot_dx は接地時のみ（config）。
"""

from dataclasses import dataclass

from . import config
from .effort import EffortBreakdown
from .episode_state import HopStepContext
from .observation import StepPhysics


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
      - self.backward_lean_penalty
      - self.forward_lean_penalty
      - self.height_penalty
    )

  @property
  def total(self) -> float:
    return self.forward + self.shaping - self.effort_penalty


class Reward:
  """片脚ホッパ向け報酬（位相ゲート付き shaping）。"""

  @staticmethod
  def _forward_component(
    dx: float,
    *,
    upright: float,
    foot_on_floor: bool,
    allow_without_contact: bool,
  ) -> float:
    dx_clipped = max(-config.MAX_DX_PER_STEP, min(config.MAX_DX_PER_STEP, float(dx)))
    if upright < config.FORWARD_MIN_UPRIGHT:
      return 0.0
    if config.FORWARD_REQUIRE_FOOT_CONTACT and not foot_on_floor:
      return 0.0
    if not allow_without_contact and not foot_on_floor:
      return 0.0
    return max(0.0, dx_clipped) * config.FORWARD_REWARD_SCALE

  @staticmethod
  def _upright_bonus(
    upright: float, *, dx: float, foot_on_floor: bool
  ) -> float:
    if config.UPRIGHT_BONUS_REQUIRE_FLIGHT and foot_on_floor:
      return 0.0
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
    imu_zaxis_x: float, *, foot_on_floor: bool, flight_steps: int
  ) -> float:
    if foot_on_floor:
      return 0.0
    if flight_steps < config.LEAN_FORWARD_MIN_FLIGHT_STEPS:
      return 0.0
    excess = max(0.0, float(imu_zaxis_x) - config.LEAN_FORWARD_THRESH)
    return excess * config.LEAN_FORWARD_PENALTY_SCALE

  @staticmethod
  def _height_penalty(imu_z: float, *, foot_on_floor: bool) -> float:
    if config.HEIGHT_PENALTY_SKIP_WHEN_STANCE and foot_on_floor:
      target = config.TARGET_IMU_Z_STANCE
      deficit = max(0.0, target - float(imu_z))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE
    if float(imu_z) < config.HEIGHT_PENALTY_FLIGHT_CRASH_Z:
      deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE * 1.5
    deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
    return deficit * config.IMU_HEIGHT_PENALTY_SCALE

  @staticmethod
  def _push_off_bonus(
    step_physics: StepPhysics,
    *,
    hop: HopStepContext,
  ) -> float:
    if not step_physics.foot_on_floor:
      return 0.0
    if step_physics.foot_dx < config.PUSH_OFF_MIN_FOOT_DX:
      return 0.0
    extending = step_physics.knee_vel < -config.PUSH_OFF_MIN_KNEE_EXT_VEL
    rising = hop.imu_dz >= config.PUSH_OFF_MIN_IMU_DZ
    if not (extending or rising):
      return 0.0
    return config.PUSH_OFF_BONUS_SCALE

  @staticmethod
  def _landing_bonus(step_physics: StepPhysics, *, hop: HopStepContext) -> float:
    if not hop.landed:
      return 0.0
    if step_physics.toe_z > config.LANDING_MAX_TOE_Z:
      return 0.0
    if step_physics.heel_z > config.LANDING_MAX_HEEL_Z:
      return 0.0
    if step_physics.imu_zaxis_x > config.LANDING_MAX_FORWARD_LEAN:
      return 0.0
    return config.LANDING_BONUS_SCALE

  def compute(
    self,
    step_physics: StepPhysics,
    *,
    hop: HopStepContext,
    effort: EffortBreakdown,
  ) -> RewardBreakdown:
    upright = step_physics.upright
    foot_on_floor = step_physics.foot_on_floor
    foot_forward_allowed = not config.FORWARD_FOOT_ONLY_WHEN_CONTACT or foot_on_floor

    forward_imu = self._forward_component(
      step_physics.dx,
      upright=upright,
      foot_on_floor=foot_on_floor,
      allow_without_contact=True,
    )
    forward_foot = self._forward_component(
      step_physics.foot_dx,
      upright=upright,
      foot_on_floor=foot_on_floor,
      allow_without_contact=foot_forward_allowed,
    )

    effort_penalty = effort.penalty if config.APPLY_EFFORT_PENALTY else 0.0

    return RewardBreakdown(
      forward_imu=forward_imu,
      forward_foot=forward_foot,
      upright_bonus=self._upright_bonus(
        upright, dx=step_physics.dx, foot_on_floor=foot_on_floor
      ),
      push_off_bonus=self._push_off_bonus(step_physics, hop=hop),
      landing_bonus=self._landing_bonus(step_physics, hop=hop),
      backward_lean_penalty=self._backward_lean_penalty(step_physics.imu_zaxis_x),
      forward_lean_penalty=self._forward_lean_penalty(
        step_physics.imu_zaxis_x,
        foot_on_floor=foot_on_floor,
        flight_steps=hop.flight_steps,
      ),
      height_penalty=self._height_penalty(
        step_physics.imu_z, foot_on_floor=foot_on_floor
      ),
      effort_penalty=effort_penalty,
      effort_power_cost=effort.power_cost,
    )
