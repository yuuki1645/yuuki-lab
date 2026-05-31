"""exp_003 のエピソード早期終了判定。

env.py が mj_step ループ内で done_reason を呼び、terminated なら残りの物理ステップを打ち切る。
終了ステップの報酬には TerminationOutcome.penalty を一度だけ加算する（reward.py 外）。

閾値・ペナルティ係数は config.py。接触の読み取りは lib/contact.py。
"""

from collections.abc import Callable
from dataclasses import dataclass

import mujoco

import config
from lib.contact import (
  has_contact_between_geoms,
  max_normal_force_between_geoms,
)

# --- 終了理由ラベル（wandb・step_info["termination_reason"] と一致）-------------
REASON_TRUNCATED = "truncated"  # train.py が最大ステップで付与。本モジュールでは判定しない
REASON_CONTACT_BASKET = "contact_basket"
REASON_CONTACT_THIGH = "contact_thigh"
REASON_CONTACT_SHANK = "contact_shank"

# 全 reason の一覧（ログ集計用）
TERMINATION_REASONS = (
  REASON_TRUNCATED,
  REASON_CONTACT_BASKET,
  REASON_CONTACT_THIGH,
  REASON_CONTACT_SHANK,
)


@dataclass(frozen=True)
class TerminationOutcome:
  """1 回の done_reason 評価結果。

  env.py は penalty を報酬に加算し、reason / contact_normal_force_n を step_info に載せる。
  """

  reason: str | None  # 終了しなければ None
  penalty: float  # 終了ステップに加算する値（通常は 0 以下）
  contact_normal_force_n: float | None = None  # floor 接触終了時のみ [N]

  @property
  def terminated(self) -> bool:
    return self.reason is not None


NOT_TERMINATED = TerminationOutcome(None, 0.0, None)


class Termination:
  """MuJoCo 状態から早期終了を判定する。

  呼び出しタイミング
  ----------------
  env.step 内の各 mj_step の直後。対象 geom が床に触れた物理ステップで即打ち切る。

  終了条件（優先順: basket → thigh_link → shank_link）
  --------
  contact_basket … basket geom が床に触れた
  contact_thigh  … thigh_link geom が床に触れた
  contact_shank  … shank_link geom が床に触れた

  ペナルティ
  ----------
  basket: 法線力 [N] に比例（config.CONTACT_FLOOR_*、フルスケール）
  thigh / shank: 同式で config.CONTACT_LINK_PENALTY_SCALE（既定 0.5）倍
  """

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
    """指定 geom と floor の接触があれば終了 outcome を返す。なければ None。"""
    if not has_contact_between_geoms(data, geom_id, self._floor_geom_id):
      return None

    normal_force_n = max_normal_force_between_geoms(
      self._model, data, geom_id, self._floor_geom_id
    )
    penalty = penalty_fn(normal_force_n)
    return TerminationOutcome(reason, penalty, normal_force_n)

  def done_reason(self, data: mujoco.MjData) -> TerminationOutcome:
    """現在の MjData に対する終了判定。"""
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

  def is_done(self, data: mujoco.MjData) -> bool:
    return self.done_reason(data).terminated
