"""エピソード内でだけ必要な状態（交互片脚歩行の位相追跡）。"""

from dataclasses import dataclass, field

import numpy as np
from lib.experiment_context import ExperimentContext


@dataclass(frozen=True)
class BipedStepContext:
  """両脚の接地・遊脚位相。"""

  left_landed: bool
  right_landed: bool
  aerial_steps: int
  both_feet_on_floor: bool
  any_foot_on_floor: bool
  single_support: bool
  single_support_side: int
  alternating_landing: bool


@dataclass
class EpisodeState:
  """エピソードをまたいで保持する歩行位相・前ステップ位置。

  advance_biped_context が着地検出・交互歩行・飛翔ステップ数を更新する。
  """

  origin_imu_x: float = 0.0
  prev_imu_x: float = 0.0
  prev_left_foot_x: float = 0.0
  prev_right_foot_x: float = 0.0
  prev_imu_z: float = 0.0
  prev_left_on_floor: bool = False
  prev_right_on_floor: bool = False
  aerial_steps: int = 0
  best_imu_x: float = 0.0
  prev_single_support_side: int = 0
  ctx: ExperimentContext | None = field(default=None, repr=False)
  prev_action: tuple[float, ...] = field(default_factory=tuple)

  def reset_forward_tracking(
    self,
    *,
    imu_x: float,
    left_foot_x: float,
    right_foot_x: float,
    imu_z: float,
    n_action: int = 12,
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
    self.prev_single_support_side = 0
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

  def advance_progress(
    self, imu_x: float, *, upright: float, single_support: bool
  ) -> float:
    """IMU +X のエピソード内最高更新量 [m]。片足支持・直立時のみカウント。"""
    if self.ctx is None:
      raise ValueError("EpisodeState.ctx must be set before advance_progress")
    if upright < self.ctx.cfg.reward.progress_min_upright:
      return 0.0
    if self.ctx.cfg.reward.progress_require_single_support and not single_support:
      return 0.0
    progress = float(np.clip(float(imu_x) - self.best_imu_x, 0.0, np.inf))
    if progress > 0.0:
      self.best_imu_x = float(imu_x)
    return progress

  @staticmethod
  def _single_support_side(left_on_floor: bool, right_on_floor: bool) -> int:
    if left_on_floor and not right_on_floor:
      return 1
    if right_on_floor and not left_on_floor:
      return -1
    return 0

  def advance_biped_context(
    self,
    *,
    left_on_floor: bool,
    right_on_floor: bool,
    imu_z: float,
  ) -> BipedStepContext:
    # 着地 = 非接地 → 接地 の立ち上がりエッジ
    left_landed = left_on_floor and not self.prev_left_on_floor
    right_landed = right_on_floor and not self.prev_right_on_floor
    any_foot = left_on_floor or right_on_floor
    both_feet = left_on_floor and right_on_floor
    single_support = (left_on_floor and not right_on_floor) or (
      right_on_floor and not left_on_floor
    )
    support_side = self._single_support_side(left_on_floor, right_on_floor)

    # 交互着地: 前ステップが反対脚支持だった状態からの着地
    alternating_landing = False
    if left_landed and self.prev_single_support_side == -1:
      alternating_landing = True  # 右支持 → 左着地
    if right_landed and self.prev_single_support_side == 1:
      alternating_landing = True  # 左支持 → 右着地

    # 両足非接地の連続ステップ数（ホップ抑制ペナルティ用）
    if any_foot:
      self.aerial_steps = 0
    else:
      self.aerial_steps += 1

    self.prev_left_on_floor = left_on_floor
    self.prev_right_on_floor = right_on_floor
    self.prev_imu_z = imu_z
    if single_support:
      self.prev_single_support_side = support_side

    return BipedStepContext(
      left_landed=left_landed,
      right_landed=right_landed,
      aerial_steps=self.aerial_steps,
      both_feet_on_floor=both_feet,
      any_foot_on_floor=any_foot,
      single_support=single_support,
      single_support_side=support_side,
      alternating_landing=alternating_landing,
    )

  def imu_dz(self, imu_z: float) -> float:
    return float(imu_z) - float(self.prev_imu_z)
