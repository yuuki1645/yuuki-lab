"""両脚バイペッド向け早期終了。"""

from collections.abc import Callable
from dataclasses import dataclass

import mujoco
import numpy as np

from . import config
from .lib.actuators import SHANK_GEOM_IDS, THIGH_GEOM_IDS
from .observation import StepPhysics

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
  def __init__(self, model: mujoco.MjModel):
    self._model = model
    self._floor_geom_id = model.geom("floor").id
    self._basket_geom_id = model.geom("basket").id
    self._thigh_geom_ids = tuple(model.geom(name).id for name in THIGH_GEOM_IDS)
    self._shank_geom_ids = tuple(model.geom(name).id for name in SHANK_GEOM_IDS)
    # mj_contactForce の出力先（ループ内で再利用）
    self._contact_wrench = np.zeros(6)

  @staticmethod
  def _is_geom_pair(
    contact: mujoco.MjContact, geom_a_id: int, geom_b_id: int
  ) -> bool:
    """geom1/geom2 の順序は MuJoCo が入れ替えることがある。"""
    return (contact.geom1 == geom_a_id and contact.geom2 == geom_b_id) or (
      contact.geom1 == geom_b_id and contact.geom2 == geom_a_id
    )

  @staticmethod
  def _has_contact_between_geoms(
    data: mujoco.MjData, geom_a_id: int, geom_b_id: int
  ) -> bool:
    """2 geom 間に接触が1つでもあるか。"""
    for contact_index in range(data.ncon):
      if Termination._is_geom_pair(
        data.contact[contact_index], geom_a_id, geom_b_id
      ):
        return True
    return False

  def _max_normal_force_between_geoms(
    self, data: mujoco.MjData, geom_a_id: int, geom_b_id: int
  ) -> float:
    """2 geom 間の接触のうち、法線力 |force[0]| の最大値 [N]。接触なしなら 0。"""
    peak_normal_force_n = 0.0
    for contact_index in range(data.ncon):
      contact = data.contact[contact_index]
      if not self._is_geom_pair(contact, geom_a_id, geom_b_id):
        continue
      mujoco.mj_contactForce(
        self._model, data, contact_index, self._contact_wrench
      )
      peak_normal_force_n = max(
        peak_normal_force_n, abs(float(self._contact_wrench[0]))
      )
    return peak_normal_force_n

  def _floor_contact_outcome(
    self,
    data: mujoco.MjData,
    *,
    geom_id: int,
    reason: str,
    penalty_fn: Callable[[float], float],
  ) -> TerminationOutcome | None:
    if not self._has_contact_between_geoms(data, geom_id, self._floor_geom_id):
      return None
    normal_force_n = self._max_normal_force_between_geoms(
      data, geom_id, self._floor_geom_id
    )
    penalty = penalty_fn(normal_force_n)
    return TerminationOutcome(reason, penalty, normal_force_n)

  def done_reason_contact(self, data: mujoco.MjData) -> TerminationOutcome:
    outcome = self._floor_contact_outcome(
      data,
      geom_id=self._basket_geom_id,
      reason=REASON_CONTACT_BASKET,
      penalty_fn=config.contact_basket_termination_penalty,
    )
    if outcome is not None:
      return outcome

    for thigh_id in self._thigh_geom_ids:
      outcome = self._floor_contact_outcome(
        data,
        geom_id=thigh_id,
        reason=REASON_CONTACT_THIGH,
        penalty_fn=config.contact_link_termination_penalty,
      )
      if outcome is not None:
        return outcome

    if config.CONTACT_SHANK_TERMINATES:
      for shank_id in self._shank_geom_ids:
        outcome = self._floor_contact_outcome(
          data,
          geom_id=shank_id,
          reason=REASON_CONTACT_SHANK,
          penalty_fn=config.contact_link_termination_penalty,
        )
        if outcome is not None:
          return outcome

    return NOT_TERMINATED

  def shank_contact_step_penalty(self, data: mujoco.MjData) -> float:
    if config.CONTACT_SHANK_TERMINATES:
      return 0.0
    total = 0.0
    for shank_id in self._shank_geom_ids:
      if not self._has_contact_between_geoms(
        data, shank_id, self._floor_geom_id
      ):
        continue
      normal_force_n = self._max_normal_force_between_geoms(
        data, shank_id, self._floor_geom_id
      )
      total += config.contact_shank_step_penalty(normal_force_n)
    return total

  @staticmethod
  def done_reason_pose(
    step_physics: StepPhysics, *, any_foot_on_floor: bool
  ) -> TerminationOutcome:
    imu_z = step_physics.imu_z
    upright = step_physics.upright
    imu_zaxis_x = step_physics.imu_zaxis_x

    min_imu_z = (
      config.MIN_IMU_Z_STANCE if any_foot_on_floor else config.MIN_IMU_Z
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
