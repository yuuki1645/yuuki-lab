"""各エピソード開始直後のウォームアップ行動（実時間ベース）。

train.py がエピソード開始から WARMUP_DURATION_S 未満のあいだ、方策の代わりに WARMUP_ACTION_FN を呼ぶ。
行動は [-1, 1]²（膝・足首）で返す。範囲外は clip される。

カスタム例（config.py で差し替え）::

  from mujoco_rl_sim.experiments.exp_002_2joint_a2c.warmup import WarmupContext, warmup_action_from_deg

  def my_warmup(ctx: WarmupContext) -> tuple[float, float]:
    return warmup_action_from_deg(knee_deg=10.0, ankle_deg=0.0)

  WARMUP_ACTION_FN = my_warmup
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from mujoco_rl_sim.experiments.exp_002_2joint_a2c.lib.ctrl import clip_policy_action

WarmupActionFn = Callable[["WarmupContext"], tuple[float, float]]

# main.xml の knee_servo / ankle_servo の ctrlrange [rad]（XML 変更時はここも合わせる）
_KNEE_CTRL_RANGE_RAD = (0.0, 1.745)
_ANKLE_CTRL_RANGE_RAD = (-0.349, 1.571)

JointName = Literal["knee", "ankle"]


@dataclass(frozen=True, slots=True)
class WarmupContext:
  """ウォームアップ行動関数へ渡すコンテキスト。"""

  obs: Sequence[float]
  elapsed_s: float  # 当該エピソード開始からの実時間 [s]
  total_env_steps: int
  episode_step: int
  episode_index: int


def _ctrl_rad_to_action(ctrl_rad: float, lo: float, hi: float) -> float:
  """目標関節角 [rad] をポリシー action [-1, 1] に変換（action_to_ctrl の逆）。"""
  span = hi - lo
  if span <= 0.0:
    raise ValueError(f"invalid ctrl range: lo={lo}, hi={hi}")
  t = (float(ctrl_rad) - lo) / span
  return 2.0 * t - 1.0


def deg_to_action(deg: float, *, joint: JointName) -> float:
  """main.xml コメントと同じ「度」表現を [-1, 1] の action に変換する。

  膝: 0°=真下（伸ばし寄り）… 100°=後屈最大
  足首: 0°=真横 … -20°=背屈最大 … +90°=底屈最大

  範囲外の角度は action が ±1 を超えることがある（resolve 時に clip）。
  """
  ctrl_rad = math.radians(deg)
  if joint == "knee":
    lo, hi = _KNEE_CTRL_RANGE_RAD
  else:
    lo, hi = _ANKLE_CTRL_RANGE_RAD
  return _ctrl_rad_to_action(ctrl_rad, lo, hi)


def knee_deg_to_action(deg: float) -> float:
  """膝の目標角 [deg] → action。"""
  return deg_to_action(deg, joint="knee")


def ankle_deg_to_action(deg: float) -> float:
  """足首の目標角 [deg] → action。"""
  return deg_to_action(deg, joint="ankle")


def warmup_action_from_deg(knee_deg: float, ankle_deg: float) -> tuple[float, float]:
  """膝・足首の目標角 [deg] から (knee_action, ankle_action) をまとめて作る。"""
  return (knee_deg_to_action(knee_deg), ankle_deg_to_action(ankle_deg))


def default_warmup_action(ctx: WarmupContext) -> tuple[float, float]:
  """既定: 膝真下 0°・足首真横 0°（main.xml の関節 0° 定義）。"""
  _ = ctx
  return warmup_action_from_deg(0.0, -3.0)


def clip_warmup_action(action: tuple[float, float]) -> tuple[float, float]:
  return (
    clip_policy_action(action[0]),
    clip_policy_action(action[1]),
  )


def resolve_warmup_action(fn: WarmupActionFn, ctx: WarmupContext) -> tuple[float, float]:
  """fn(ctx) を呼び、ポリシーと同様 [-1, 1]² にクリップして返す。"""
  return clip_warmup_action(fn(ctx))
