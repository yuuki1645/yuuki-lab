"""両脚前進 PPO 向けステップ報酬。"""

from dataclasses import dataclass

from . import config
from .effort import EffortBreakdown
from .episode_state import BipedStepContext
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
  def _knee_hyperflex_penalty(step_physics: StepPhysics) -> float:
    if config.KNEE_HYPERFLEX_AERIAL_ONLY and step_physics.any_foot_on_floor:
      return 0.0
    knee = max(
      step_physics.left_knee_angle, step_physics.right_knee_angle
    )
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
  def _forward_foot_sum(step_physics: StepPhysics) -> float:
    total = 0.0
    if step_physics.left_foot_on_floor:
      total += max(0.0, step_physics.left_foot_dx)
    if step_physics.right_foot_on_floor:
      total += max(0.0, step_physics.right_foot_dx)
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
    step_physics: StepPhysics,
    *,
    biped: BipedStepContext,
    effort: EffortBreakdown,
    progress_m: float = 0.0,
  ) -> RewardBreakdown:
    upright = step_physics.upright
    any_foot = step_physics.any_foot_on_floor

    imu_forward_scale = self._forward_imu_lean_multiplier(
      step_physics.imu_zaxis_x, any_foot_on_floor=any_foot
    )
    forward_imu = self._forward_component(
      step_physics.dx,
      upright=upright,
      allow_without_contact=True,
      contact_ok=any_foot,
      scale=imu_forward_scale,
    )

    foot_dx = self._forward_foot_sum(step_physics)
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
      upright_bonus=self._upright_bonus(upright, dx=step_physics.dx),
      push_off_bonus=0.0,
      landing_bonus=0.0,
      backward_lean_penalty=self._backward_lean_penalty(step_physics.imu_zaxis_x),
      forward_lean_penalty=self._forward_lean_penalty(
        step_physics.imu_zaxis_x,
        any_foot_on_floor=any_foot,
        aerial_steps=biped.aerial_steps,
      ),
      height_penalty=self._height_penalty(
        step_physics.imu_z, any_foot_on_floor=any_foot
      ),
      flight_duration_penalty=self._aerial_duration_penalty(
        any_foot_on_floor=any_foot, aerial_steps=biped.aerial_steps
      ),
      progress_bonus=self._progress_bonus(progress_m),
      knee_hyperflex_penalty=self._knee_hyperflex_penalty(step_physics),
      effort_penalty=effort_penalty,
      effort_power_cost=effort.power_cost,
    )
