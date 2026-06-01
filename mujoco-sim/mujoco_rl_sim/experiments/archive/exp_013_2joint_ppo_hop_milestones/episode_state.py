"""エピソード内でだけ必要な状態（MuJoCo には載らないもの）。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HopStepContext:
  """報酬の位相判定用（立脚 / 飛翔 / 着地）。"""

  landed: bool
  flight_steps: int
  imu_dz: float


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
  next_milestone_idx: int = 0
  prev_action: tuple[float, float] = (0.0, 0.0)

  def reset_forward_tracking(
    self, *, imu_x: float, foot_x: float, imu_z: float
  ) -> None:
    """reset() で呼ぶ。前進量・ホップ位相の差分基準をリセットする。"""
    self.origin_imu_x = imu_x
    self.best_imu_x = imu_x
    self.next_milestone_idx = 0
    self.prev_imu_x = imu_x
    self.prev_foot_x = foot_x
    self.prev_imu_z = imu_z
    self.prev_foot_on_floor = False
    self.flight_steps = 0

  def advance_imu_x(self, imu_x: float) -> float:
    dx = imu_x - self.prev_imu_x
    self.prev_imu_x = imu_x
    return dx

  def advance_milestones(self, imu_x: float, *, upright: float) -> float:
    """origin からの累積前進で通過マイルストーンごとに 1 回ボーナス（exp_013）。"""
    import config

    if upright < config.MILESTONE_MIN_UPRIGHT:
      return 0.0
    rel_x = float(imu_x) - self.origin_imu_x
    bonus = 0.0
    while (
      self.next_milestone_idx < len(config.MILESTONE_DISTANCES_M)
      and rel_x >= config.MILESTONE_DISTANCES_M[self.next_milestone_idx]
    ):
      bonus += config.MILESTONE_BONUS
      self.next_milestone_idx += 1
    return bonus

  def advance_progress(self, imu_x: float, *, upright: float) -> float:
    """直立を保ちながら更新した best_imu_x 超過分 [m]（exp_010 進捗報酬用）。"""
    import config

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
    self, *, foot_on_floor: bool, imu_z: float
  ) -> HopStepContext:
    """着地エッジ・連続飛翔ステップ数・IMU 高さ変化を更新する。"""
    landed = foot_on_floor and not self.prev_foot_on_floor
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
    )
