"""exp_004 のエピソード早期終了（姿勢 exp_001 + 接触 exp_003）。

接触: env の mj_step ループ内で判定（即打ち切り）。
姿勢: 制御ステップ末の StepPhysics で判定（接触未終了時のみ）。

終了ステップの報酬には TerminationOutcome.penalty を一度だけ加算する。
"""

from collections.abc import Callable
from dataclasses import dataclass

import mujoco

from . import config
from .lib.contact import (
  has_contact_between_geoms,
  max_normal_force_between_geoms,
)
from .observation import StepPhysics

REASON_TRUNCATED = "truncated"
# 姿勢（exp_001）
REASON_IMU_Z = "imu_z"
REASON_LOW_UPRIGHT = "low_upright"
REASON_BACKWARD_LEAN = "backward_lean"
# 接触（exp_003）
REASON_CONTACT_BASKET = "contact_basket"
REASON_CONTACT_THIGH = "contact_thigh"
REASON_CONTACT_SHANK = "contact_shank"

TERMINATION_REASONS = (
  REASON_TRUNCATED,
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_BACKWARD_LEAN,
  REASON_CONTACT_BASKET,
  REASON_CONTACT_THIGH,
  REASON_CONTACT_SHANK,
)


@dataclass(frozen=True)
class TerminationOutcome:
  reason: str | None
  penalty: float
  contact_normal_force_n: float | None = None

  @property
  def terminated(self) -> bool:
    return self.reason is not None


NOT_TERMINATED = TerminationOutcome(None, 0.0, None)


class Termination:
  """MuJoCo 状態から早期終了を判定する。"""

  def __init__(self, model: mujoco.MjModel):
    self._model = model
    self._floor_geom_id = model.geom("floor").id
    self._basket_geom_id = model.geom("basket").id
    self._thigh_geom_id = model.geom("thigh_link").id
    self._shank_geom_id = model.geom("shank_link").id

  def _floor_contact_outcome(
    self,
    data: mujoco.MjData,
    *,
    geom_id: int,
    reason: str,
    penalty_fn: Callable[[float], float],
  ) -> TerminationOutcome | None:
    if not has_contact_between_geoms(data, geom_id, self._floor_geom_id):
      return None

    normal_force_n = max_normal_force_between_geoms(
      self._model, data, geom_id, self._floor_geom_id
    )
    penalty = penalty_fn(normal_force_n)
    return TerminationOutcome(reason, penalty, normal_force_n)

  def done_reason_contact(self, data: mujoco.MjData) -> TerminationOutcome:
    """物理ステップごとの geom−floor 接触判定（basket → thigh → shank）。"""
    for geom_id, reason, penalty_fn in (
      (self._basket_geom_id, REASON_CONTACT_BASKET, config.contact_basket_termination_penalty),
      (self._thigh_geom_id, REASON_CONTACT_THIGH, config.contact_link_termination_penalty),
      (self._shank_geom_id, REASON_CONTACT_SHANK, config.contact_link_termination_penalty),
    ):
      outcome = self._floor_contact_outcome(
        data, geom_id=geom_id, reason=reason, penalty_fn=penalty_fn
      )
      if outcome is not None:
        return outcome
    return NOT_TERMINATED

  @staticmethod
  def done_reason_pose(step_physics: StepPhysics) -> TerminationOutcome:
    """制御ステップ末の姿勢崩れ（exp_001 閾値）。固定ペナルティ。"""
    imu_z = step_physics.imu_z
    upright = step_physics.upright
    imu_zaxis_x = step_physics.imu_zaxis_x

    if imu_z < config.MIN_IMU_Z:
      return TerminationOutcome(REASON_IMU_Z, config.POSE_TERMINATION_PENALTY, None)
    if upright < config.MIN_IMU_UPRIGHT:
      return TerminationOutcome(REASON_LOW_UPRIGHT, config.POSE_TERMINATION_PENALTY, None)
    if imu_zaxis_x < -config.MAX_BACKWARD_LEAN:
      return TerminationOutcome(REASON_BACKWARD_LEAN, config.POSE_TERMINATION_PENALTY, None)
    return NOT_TERMINATED

  def is_done_contact(self, data: mujoco.MjData) -> bool:
    return self.done_reason_contact(data).terminated
