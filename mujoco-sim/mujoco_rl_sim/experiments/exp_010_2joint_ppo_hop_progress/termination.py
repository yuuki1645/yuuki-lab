"""exp_008 の早期終了（片脚ホッパ向け）。

接触:
  - basket / thigh … 即終了（従来どおり）
  - shank … 終了せずステップペナルティのみ（config.CONTACT_SHANK_TERMINATES=False）

姿勢: 立脚中は MIN_IMU_Z を緩和（押し込み許容）。
"""

from collections.abc import Callable
from dataclasses import dataclass

import mujoco

import config
from lib.contact import (
  has_contact_between_geoms,
  max_normal_force_between_geoms,
)
from observation import StepPhysics

REASON_TRUNCATED = "truncated"
REASON_IMU_Z = "imu_z"
REASON_LOW_UPRIGHT = "low_upright"
REASON_BACKWARD_LEAN = "backward_lean"
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
    """物理ステップごとの終了判定（basket / thigh のみ即終了）。"""
    for geom_id, reason, penalty_fn in (
      (self._basket_geom_id, REASON_CONTACT_BASKET, config.contact_basket_termination_penalty),
      (self._thigh_geom_id, REASON_CONTACT_THIGH, config.contact_link_termination_penalty),
    ):
      outcome = self._floor_contact_outcome(
        data, geom_id=geom_id, reason=reason, penalty_fn=penalty_fn
      )
      if outcome is not None:
        return outcome

    if config.CONTACT_SHANK_TERMINATES:
      outcome = self._floor_contact_outcome(
        data,
        geom_id=self._shank_geom_id,
        reason=REASON_CONTACT_SHANK,
        penalty_fn=config.contact_link_termination_penalty,
      )
      if outcome is not None:
        return outcome

    return NOT_TERMINATED

  def shank_contact_step_penalty(self, data: mujoco.MjData) -> float:
    """下腿−床接触時のステップペナルティ（終了しない）。"""
    if config.CONTACT_SHANK_TERMINATES:
      return 0.0
    if not has_contact_between_geoms(
      data, self._shank_geom_id, self._floor_geom_id
    ):
      return 0.0
    normal_force_n = max_normal_force_between_geoms(
      self._model, data, self._shank_geom_id, self._floor_geom_id
    )
    return config.contact_shank_step_penalty(normal_force_n)

  @staticmethod
  def done_reason_pose(
    step_physics: StepPhysics, *, foot_on_floor: bool
  ) -> TerminationOutcome:
    imu_z = step_physics.imu_z
    upright = step_physics.upright
    imu_zaxis_x = step_physics.imu_zaxis_x

    min_imu_z = (
      config.MIN_IMU_Z_STANCE if foot_on_floor else config.MIN_IMU_Z
    )
    if imu_z < min_imu_z:
      return TerminationOutcome(REASON_IMU_Z, config.POSE_TERMINATION_PENALTY, None)
    if upright < config.MIN_IMU_UPRIGHT:
      return TerminationOutcome(REASON_LOW_UPRIGHT, config.POSE_TERMINATION_PENALTY, None)
    if imu_zaxis_x < -config.MAX_BACKWARD_LEAN:
      return TerminationOutcome(
        REASON_BACKWARD_LEAN, config.POSE_TERMINATION_PENALTY, None
      )
    return NOT_TERMINATED

  def is_done_contact(self, data: mujoco.MjData) -> bool:
    return self.done_reason_contact(data).terminated
