from dataclasses import dataclass

import mujoco

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.lib.contact import (
  has_contact_between_geoms,
  max_normal_force_between_geoms,
)

# done_reason / wandb 用の終了理由ラベル
REASON_IMU_Z = "imu_z"  # IMU 高さが下限を下回った（しゃがみ／倒れ込み）
REASON_LOW_UPRIGHT = "low_upright"  # 体軸が鉛直から大きく外れた（横倒しなど）
REASON_BACKWARD_LEAN = "backward_lean"  # 後傾しすぎ（−X 方向へ倒れ）
REASON_TRUNCATED = "truncated"  # 最大ステップ到達（train.py で判定。本クラスでは未使用）
REASON_CONTACT_BASKET = "contact_basket"  # basket（頭相当）が床に接触

TERMINATION_REASONS = (
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_BACKWARD_LEAN,
  REASON_TRUNCATED,
  REASON_CONTACT_BASKET,
)

FIXED_TERMINATION_REASONS = (
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_BACKWARD_LEAN,
  REASON_TRUNCATED,
)


@dataclass(frozen=True)
class TerminationOutcome:
  """終了判定の結果。終了しないとき reason=None, penalty=0。"""

  reason: str | None
  penalty: float
  contact_normal_force_n: float | None = None

  @property
  def terminated(self) -> bool:
    return self.reason is not None


NOT_TERMINATED = TerminationOutcome(None, 0.0, None)


class Termination:
  """エピソード早期終了（転倒・姿勢崩れ・頭部接触）の判定。

  mj_step 後の MjData から評価する。判定順（先頭のみ採用）:
    1. contact_basket … basket geom と床の接触（ペナルティは法線力に線形）
    2. imu_z          … IMU 高さが下限未満
    3. low_upright    … 体軸の直立度不足
    4. backward_lean  … 後傾しすぎ

  最大ステップ打ち切りは train.py（REASON_TRUNCATED）。
  """

  def __init__(self, model: mujoco.MjModel):
    self._model = model
    self._floor_geom_id = model.geom("floor").id
    self._basket_geom_id = model.geom("basket").id

    missing = [
      reason
      for reason in FIXED_TERMINATION_REASONS
      if reason not in config.TERMINATION_PENALTIES
    ]
    if missing:
      raise ValueError(
        "config.TERMINATION_PENALTIES missing keys for: " + ", ".join(missing)
      )

  def _fixed_penalty_outcome(self, reason: str) -> TerminationOutcome:
    return TerminationOutcome(reason, config.TERMINATION_PENALTIES[reason], None)

  def _basket_floor_contact_outcome(self, data: mujoco.MjData) -> TerminationOutcome | None:
    if not has_contact_between_geoms(data, self._basket_geom_id, self._floor_geom_id):
      return None

    normal_force_n = max_normal_force_between_geoms(
      self._model, data, self._basket_geom_id, self._floor_geom_id
    )
    penalty = config.contact_basket_termination_penalty(normal_force_n)
    return TerminationOutcome(REASON_CONTACT_BASKET, penalty, normal_force_n)

  def done_reason(self, data: mujoco.MjData) -> TerminationOutcome:
    """最初に満たした終了条件。終了しない場合は NOT_TERMINATED。"""
    basket_contact = self._basket_floor_contact_outcome(data)
    if basket_contact is not None:
      return basket_contact

    imu_z = float(data.site("imu_site").xpos[2])
    imu_zaxis = data.sensor("imu_zaxis").data
    upright = float(imu_zaxis[2])
    imu_zaxis_x = float(imu_zaxis[0])

    if imu_z < config.MIN_IMU_Z:
      return self._fixed_penalty_outcome(REASON_IMU_Z)

    if upright < config.MIN_IMU_UPRIGHT:
      return self._fixed_penalty_outcome(REASON_LOW_UPRIGHT)

    if imu_zaxis_x < -config.MAX_BACKWARD_LEAN:
      return self._fixed_penalty_outcome(REASON_BACKWARD_LEAN)

    return NOT_TERMINATED

  def is_done(self, data: mujoco.MjData) -> bool:
    return self.done_reason(data).terminated
