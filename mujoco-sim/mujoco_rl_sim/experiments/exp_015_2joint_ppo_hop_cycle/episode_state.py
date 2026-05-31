"""エピソード内でだけ必要な状態（MuJoCo には載らないもの）。"""

from dataclasses import dataclass

import config


@dataclass(frozen=True)
class HopStepContext:
  """報酬の位相判定用（立脚 / 飛翔 / 着地）。"""

  landed: bool
  flight_steps: int
  imu_dz: float
  hop_cycle_bonus: float = 0.0


@dataclass
class EpisodeState:
  """エピソードをまたいで保持する観測・報酬用の状態。"""

  origin_imu_x: float = 0.0
  prev_imu_x: float = 0.0
  prev_foot_x: float = 0.0
  prev_imu_z: float = 0.0
  prev_foot_on_floor: bool = False
  flight_steps: int = 0
  best_imu_x: float = 0.0
  prev_action: tuple[float, float] = (0.0, 0.0)
  cycle_start_imu_x: float = 0.0
  flight_steps_at_landing: int = 0

  def reset_forward_tracking(
    self, *, imu_x: float, foot_x: float, imu_z: float
  ) -> None:
    """reset() で呼ぶ。前進量・ホップ位相の差分基準をリセットする。"""
    self.origin_imu_x = imu_x
    self.best_imu_x = imu_x
    self.prev_imu_x = imu_x
    self.prev_foot_x = foot_x
    self.prev_imu_z = imu_z
    self.prev_foot_on_floor = False
    self.flight_steps = 0
    self.cycle_start_imu_x = imu_x
    self.flight_steps_at_landing = 0

  def advance_imu_x(self, imu_x: float) -> float:
    dx = imu_x - self.prev_imu_x
    self.prev_imu_x = imu_x
    return dx

  def advance_progress(self, imu_x: float, *, upright: float) -> float:
    """直立を保ちながら更新した best_imu_x 超過分 [m]（exp_010 進捗報酬用）。"""
    if upright < config.PROGRESS_MIN_UPRIGHT:
      return 0.0
    progress = max(0.0, float(imu_x) - self.best_imu_x)
    if progress > 0.0:
      self.best_imu_x = float(imu_x)
    return progress

  def advance_foot_x(self, foot_x: float) -> float:
    foot_dx = foot_x - self.prev_foot_x
    self.prev_foot_x = foot_x
    return foot_dx

  def advance_hop_context(
    self,
    *,
    foot_on_floor: bool,
    imu_z: float,
    imu_x: float,
    upright: float,
    imu_zaxis_x: float,
  ) -> HopStepContext:
    """着地エッジ・連続飛翔ステップ数・IMU 高さ変化・周期完了ボーナスを更新する。"""
    landed = foot_on_floor and not self.prev_foot_on_floor
    takeoff = (not foot_on_floor) and self.prev_foot_on_floor
    if takeoff:
      self.cycle_start_imu_x = float(imu_x)

    hop_cycle_bonus = 0.0
    if landed:
      self.flight_steps_at_landing = self.flight_steps
      cycle_dx = float(imu_x) - self.cycle_start_imu_x
      if (
        self.flight_steps_at_landing >= config.HOP_CYCLE_MIN_FLIGHT_STEPS
        and cycle_dx >= config.HOP_CYCLE_MIN_DX_M
        and upright >= config.HOP_CYCLE_MIN_UPRIGHT
        and abs(float(imu_zaxis_x)) <= config.HOP_CYCLE_MAX_LANDING_LEAN
      ):
        hop_cycle_bonus = config.HOP_CYCLE_BONUS

    if foot_on_floor:
      self.flight_steps = 0
    else:
      self.flight_steps += 1
    imu_dz = imu_z - self.prev_imu_z
    self.prev_foot_on_floor = foot_on_floor
    self.prev_imu_z = imu_z
    return HopStepContext(
      landed=landed,
      flight_steps=self.flight_steps,
      imu_dz=imu_dz,
      hop_cycle_bonus=hop_cycle_bonus,
    )
