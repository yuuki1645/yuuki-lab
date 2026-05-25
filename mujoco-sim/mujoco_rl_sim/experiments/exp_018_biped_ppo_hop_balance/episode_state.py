"""エピソード内でだけ必要な状態。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BipedStepContext:
  """両脚の接地・遊脚位相。"""

  left_landed: bool
  right_landed: bool
  aerial_steps: int
  both_feet_on_floor: bool
  any_foot_on_floor: bool


@dataclass
class EpisodeState:
  origin_imu_x: float = 0.0
  prev_imu_x: float = 0.0
  prev_left_foot_x: float = 0.0
  prev_right_foot_x: float = 0.0
  prev_imu_z: float = 0.0
  prev_left_on_floor: bool = False
  prev_right_on_floor: bool = False
  aerial_steps: int = 0
  best_imu_x: float = 0.0
  prev_action: tuple[float, ...] = field(default_factory=lambda: (0.0,) * 10)

  def reset_forward_tracking(
    self,
    *,
    imu_x: float,
    left_foot_x: float,
    right_foot_x: float,
    imu_z: float,
    n_action: int = 10,
  ) -> None:
    self.origin_imu_x = imu_x
    self.best_imu_x = imu_x
    self.prev_imu_x = imu_x
    self.prev_left_foot_x = left_foot_x
    self.prev_right_foot_x = right_foot_x
    self.prev_imu_z = imu_z
    self.prev_left_on_floor = False
    self.prev_right_on_floor = False
    self.aerial_steps = 0
    self.prev_action = (0.0,) * n_action

  def advance_imu_x(self, imu_x: float) -> float:
    dx = imu_x - self.prev_imu_x
    self.prev_imu_x = imu_x
    return dx

  def advance_foot_dx(self, left_foot_x: float, right_foot_x: float) -> tuple[float, float]:
    left_dx = left_foot_x - self.prev_left_foot_x
    right_dx = right_foot_x - self.prev_right_foot_x
    self.prev_left_foot_x = left_foot_x
    self.prev_right_foot_x = right_foot_x
    return left_dx, right_dx

  def advance_progress(self, imu_x: float, *, upright: float) -> float:
    from . import config

    if upright < config.PROGRESS_MIN_UPRIGHT:
      return 0.0
    progress = max(0.0, float(imu_x) - self.best_imu_x)
    if progress > 0.0:
      self.best_imu_x = float(imu_x)
    return progress

  def advance_biped_context(
    self,
    *,
    left_on_floor: bool,
    right_on_floor: bool,
    imu_z: float,
  ) -> BipedStepContext:
    left_landed = left_on_floor and not self.prev_left_on_floor
    right_landed = right_on_floor and not self.prev_right_on_floor
    any_foot = left_on_floor or right_on_floor
    both_feet = left_on_floor and right_on_floor
    if any_foot:
      self.aerial_steps = 0
    else:
      self.aerial_steps += 1
    self.prev_left_on_floor = left_on_floor
    self.prev_right_on_floor = right_on_floor
    self.prev_imu_z = imu_z
    return BipedStepContext(
      left_landed=left_landed,
      right_landed=right_landed,
      aerial_steps=self.aerial_steps,
      both_feet_on_floor=both_feet,
      any_foot_on_floor=any_foot,
    )
