from dataclasses import dataclass


@dataclass
class EpisodeState:
  """エピソードをまたいで保持する観測・報酬用の状態。"""

  origin_imu_x: float = 0.0
  prev_imu_x: float = 0.0
  prev_action: tuple[float, float] = (0.0, 0.0)

  def reset_imu_tracking(self, imu_x: float) -> None:
    self.origin_imu_x = imu_x
    self.prev_imu_x = imu_x

  def advance_imu_x(self, imu_x: float) -> float:
    dx = imu_x - self.prev_imu_x
    self.prev_imu_x = imu_x
    return dx
