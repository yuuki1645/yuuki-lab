"""両脚バイペッド向け早期終了。"""

from dataclasses import dataclass

import mujoco
import numpy as np

import config
from lib.actuators import LEFT_FOOT_GEOM, RIGHT_FOOT_GEOM, SHANK_GEOM_IDS, THIGH_GEOM_IDS
from lib.pose import pose_metrics

REASON_TRUNCATED = "truncated"
REASON_IMU_Z = "imu_z"
REASON_LOW_UPRIGHT = "low_upright"
REASON_BACKWARD_LEAN = "backward_lean"
REASON_CONTACT_BASKET = "contact_basket"
REASON_CONTACT_THIGH = "contact_thigh"
REASON_CONTACT_SHANK = "contact_shank"

# MuJoCo の位置/ベクトルは [x, y, z] の順で格納される。
WORLD_X = 0
WORLD_Y = 1
WORLD_Z = 2

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
    self._left_foot_geom_id = model.geom(LEFT_FOOT_GEOM).id
    self._right_foot_geom_id = model.geom(RIGHT_FOOT_GEOM).id
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

  @staticmethod
  def _floor_termination_penalty(
    normal_force_n: float, *, penalty_scale: float = 1.0
  ) -> float:
    """床接触の終了ペナルティ。法線力 [N] に応じて base + per_N * excess。"""
    FLOOR_PENALTY_BASE = -20.0
    FLOOR_PENALTY_PER_N = -0.016
    FLOOR_MIN_FORCE_N = 0.0
    FLOOR_FORCE_CAP_N = 10_000.0
    FLOOR_PENALTY_MIN = -200.0

    scale = float(penalty_scale)
    
    capped_span = float(
      np.clip(FLOOR_FORCE_CAP_N - FLOOR_MIN_FORCE_N, 0.0, np.inf)
    )
    excess_force_n = float(
      np.clip(float(normal_force_n) - FLOOR_MIN_FORCE_N, 0.0, capped_span)
    )
    penalty = scale * (
      FLOOR_PENALTY_BASE + FLOOR_PENALTY_PER_N * excess_force_n
    )
    return float(np.clip(penalty, scale * FLOOR_PENALTY_MIN, np.inf))

  @staticmethod
  def _shank_step_penalty(normal_force_n: float) -> float:
    SHANK_STEP_PENALTY_SCALE = 1.0

    return SHANK_STEP_PENALTY_SCALE * Termination._floor_termination_penalty(
      normal_force_n, penalty_scale=SHANK_STEP_PENALTY_SCALE
    )

  def _floor_contact_outcome(
    self,
    data: mujoco.MjData,
    *,
    geom_id: int,
    reason: str,
  ) -> TerminationOutcome | None:
    BASKET_PENALTY_SCALE = 1.0
    LINK_PENALTY_SCALE = 0.5

    if not self._has_contact_between_geoms(data, geom_id, self._floor_geom_id):
      return None
    
    normal_force_n = self._max_normal_force_between_geoms(
      data, geom_id, self._floor_geom_id
    )

    if reason == REASON_CONTACT_BASKET:
      penalty_scale = BASKET_PENALTY_SCALE
    elif reason == REASON_CONTACT_THIGH or reason == REASON_CONTACT_SHANK:
      penalty_scale = LINK_PENALTY_SCALE
    else:
      penalty_scale = 1.0

    penalty = self._floor_termination_penalty(
      normal_force_n, penalty_scale=penalty_scale
    )

    return TerminationOutcome(reason, penalty, normal_force_n)

  def done_reason_contact(self, data: mujoco.MjData) -> TerminationOutcome:
    outcome = self._floor_contact_outcome(
      data,
      geom_id=self._basket_geom_id,
      reason=REASON_CONTACT_BASKET,
    )
    if outcome is not None:
      return outcome

    for thigh_id in self._thigh_geom_ids:
      outcome = self._floor_contact_outcome(
        data,
        geom_id=thigh_id,
        reason=REASON_CONTACT_THIGH,
      )
      if outcome is not None:
        return outcome

    if config.CONTACT_SHANK_TERMINATES:
      for shank_id in self._shank_geom_ids:
        outcome = self._floor_contact_outcome(
          data,
          geom_id=shank_id,
          reason=REASON_CONTACT_SHANK,
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
      total += self._shank_step_penalty(normal_force_n)

    return total

  def done_reason_pose(
    self, data: mujoco.MjData
  ) -> TerminationOutcome:
    # ここだけ読めば「何を見て、どの閾値で落とすか」が分かるようにする。

    # imu_site の世界 Z [m]。これ未満で転倒終了（低すぎ＝しゃがみすぎ／倒れ）。
    MIN_IMU_Z = 0.3
    # 足が床についているときの imu_z 下限 [m]（Viewer 参考平面と同じ高さ）。
    MIN_IMU_Z_STANCE = 0.3
    # imu_zaxis の Z 成分（上向き成分）。1 に近いほど直立。これ未満で姿勢不良終了。
    MIN_IMU_UPRIGHT = 0.52
    # ボディ +X への前傾射影がこれ未満（後傾）で終了。ヨーで imu_zaxis_x に逃げられない。
    MAX_BACKWARD_LEAN_BODY = config.MAX_BACKWARD_LEAN_BODY
    # 上記いずれかの理由でエピソード終了したときに報酬へ加算するペナルティ。
    POSE_TERMINATION_PENALTY = -30.0

    imu_z = float(data.site("imu_site").xpos[WORLD_Z])
    imu_zaxis = data.sensor("imu_zaxis").data
    upright = float(imu_zaxis[WORLD_Z])
    lean_fwd_body, _, _ = pose_metrics(imu_zaxis, data)

    any_foot_on_floor = self._has_contact_between_geoms(
      data, self._left_foot_geom_id, self._floor_geom_id
    ) or self._has_contact_between_geoms(
      data, self._right_foot_geom_id, self._floor_geom_id
    )

    min_imu_z = MIN_IMU_Z_STANCE if any_foot_on_floor else MIN_IMU_Z
    if imu_z < min_imu_z:
      return TerminationOutcome(REASON_IMU_Z, POSE_TERMINATION_PENALTY, None)

    if upright < MIN_IMU_UPRIGHT:
      return TerminationOutcome(
        REASON_LOW_UPRIGHT, POSE_TERMINATION_PENALTY, None
      )

    if lean_fwd_body < -MAX_BACKWARD_LEAN_BODY:
      return TerminationOutcome(
        REASON_BACKWARD_LEAN, POSE_TERMINATION_PENALTY, None
      )

    return NOT_TERMINATED

  def is_done_contact(self, data: mujoco.MjData) -> bool:
    return self.done_reason_contact(data).terminated
