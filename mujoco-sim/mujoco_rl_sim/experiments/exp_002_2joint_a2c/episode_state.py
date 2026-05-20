"""エピソード内でだけ必要な状態（MuJoCo には載らないもの）。"""

from dataclasses import dataclass


@dataclass
class EpisodeState:
  """エピソードをまたいで保持する観測・報酬用の状態。"""

  origin_imu_x: float = 0.0  # reset 時の IMU X。rel_imu_x の基準
  prev_imu_x: float = 0.0  # 直前制御ステップの IMU X。dx = imu_x - prev
  prev_foot_x: float = 0.0  # 直前制御ステップの foot_site X。foot_dx = foot_x - prev
  prev_action: tuple[float, float] = (0.0, 0.0)  # 観測の prev_*_action 用

  def reset_forward_tracking(self, *, imu_x: float, foot_x: float) -> None:
    """reset() で呼ぶ。前進量 dx / foot_dx の差分基準をリセットする。"""
    self.origin_imu_x = imu_x
    self.prev_imu_x = imu_x
    self.prev_foot_x = foot_x

  def reset_imu_tracking(self, imu_x: float) -> None:
    """reset_imu_tracking の互換。foot は imu と同値で初期化（非推奨）。"""
    self.reset_forward_tracking(imu_x=imu_x, foot_x=imu_x)

  def advance_imu_x(self, imu_x: float) -> float:
    """1 制御ステップ分の IMU X 変位 [m] を返し、prev を更新する。"""
    dx = imu_x - self.prev_imu_x
    self.prev_imu_x = imu_x
    return dx

  def advance_foot_x(self, foot_x: float) -> float:
    """1 制御ステップ分の foot_site X 変位 [m] を返し、prev を更新する。"""
    foot_dx = foot_x - self.prev_foot_x
    self.prev_foot_x = foot_x
    return foot_dx
