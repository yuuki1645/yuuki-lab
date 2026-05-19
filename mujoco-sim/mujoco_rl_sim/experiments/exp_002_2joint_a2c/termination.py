"""exp_002 のエピソード早期終了判定。

env.py が mj_step ループ内で done_reason を呼び、terminated なら残りの物理ステップを打ち切る。
終了ステップの報酬には TerminationOutcome.penalty を一度だけ加算する（reward.py 外）。

閾値・ペナルティ係数は config.py。接触の読み取りは lib/contact.py。
"""

from dataclasses import dataclass

import mujoco

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.lib.contact import (
  has_contact_between_geoms,
  max_normal_force_between_geoms,
)

# --- 終了理由ラベル（wandb・step_info["termination_reason"] と一致）-------------
REASON_TRUNCATED = "truncated"  # train.py が最大ステップで付与。本モジュールでは判定しない
REASON_CONTACT_BASKET = "contact_basket"

# 全 reason の一覧（ログ集計用）
TERMINATION_REASONS = (
  REASON_TRUNCATED,
  REASON_CONTACT_BASKET,
)


@dataclass(frozen=True)
class TerminationOutcome:
  """1 回の done_reason 評価結果。

  env.py は penalty を報酬に加算し、reason / contact_normal_force_n を step_info に載せる。
  """

  reason: str | None  # 終了しなければ None
  penalty: float  # 終了ステップに加算する値（通常は 0 以下）
  contact_normal_force_n: float | None = None  # contact_basket 時のみ [N]

  @property
  def terminated(self) -> bool:
    return self.reason is not None


NOT_TERMINATED = TerminationOutcome(None, 0.0, None)


class Termination:
  """MuJoCo 状態から早期終了を判定する。

  呼び出しタイミング
  ----------------
  env.step 内の各 mj_step の直後。basket が床に触れた物理ステップで即打ち切る。

  終了条件
  --------
  contact_basket … XML の basket geom が床に触れた（頭部着地相当）

  ペナルティ
  ----------
  contact_basket: 接触の法線力 [N] に比例（config.CONTACT_BASKET_*）
  """

  def __init__(self, model: mujoco.MjModel):
    self._model = model
    self._floor_geom_id = model.geom("floor").id
    self._basket_geom_id = model.geom("basket").id

  def _basket_floor_contact_outcome(self, data: mujoco.MjData) -> TerminationOutcome | None:
    """basket−floor 接触があれば終了 outcome を返す。なければ None。

    複数接触点があるときは法線力 |force[0]| の最大値を衝撃の強さとみなす。
    力の単位は N（MuJoCo 既定の MKS）。
    """
    if not has_contact_between_geoms(data, self._basket_geom_id, self._floor_geom_id):
      return None

    normal_force_n = max_normal_force_between_geoms(
      self._model, data, self._basket_geom_id, self._floor_geom_id
    )
    penalty = config.contact_basket_termination_penalty(normal_force_n)
    return TerminationOutcome(REASON_CONTACT_BASKET, penalty, normal_force_n)

  def done_reason(self, data: mujoco.MjData) -> TerminationOutcome:
    """現在の MjData に対する終了判定。"""
    basket_contact = self._basket_floor_contact_outcome(data)
    if basket_contact is not None:
      return basket_contact
    return NOT_TERMINATED

  def is_done(self, data: mujoco.MjData) -> bool:
    return self.done_reason(data).terminated
