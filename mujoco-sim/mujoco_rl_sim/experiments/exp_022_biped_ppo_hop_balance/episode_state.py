"""エピソード内でだけ必要な状態。"""

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class BipedStepContext:
  """両脚位相（IMU 高さベース。contact 走査なし）。"""

  in_stance: bool
  entered_stance: bool
  aerial_steps: int


@dataclass
class EpisodeState:
  origin_imu_x: float = 0.0
  prev_imu_x: float = 0.0
  prev_left_foot_x: float = 0.0
  prev_right_foot_x: float = 0.0
  prev_imu_z: float = 0.0
  prev_in_stance: bool = False
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
    self.prev_in_stance = False
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
    import config

    if upright < config.PROGRESS_MIN_UPRIGHT:
      return 0.0
    progress = float(np.clip(float(imu_x) - self.best_imu_x, 0.0, np.inf))
    if progress > 0.0:
      self.best_imu_x = float(imu_x)
    return progress

  def advance_biped_context(self, *, imu_z: float) -> BipedStepContext:
    import config

    in_stance = float(imu_z) < config.STANCE_IMU_Z_THRESHOLD
    entered_stance = in_stance and not self.prev_in_stance
    if in_stance:
      self.aerial_steps = 0
    else:
      self.aerial_steps += 1
    self.prev_in_stance = in_stance
    self.prev_imu_z = imu_z
    return BipedStepContext(
      in_stance=in_stance,
      entered_stance=entered_stance,
      aerial_steps=self.aerial_steps,
    )
