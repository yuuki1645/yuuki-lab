"""学習開始直後のウォームアップ行動（実時間ベース）。

train.py が WARMUP_DURATION_S 未満のあいだ、方策の代わりに WARMUP_ACTION_FN を呼ぶ。
行動は [-1, 1]²（膝・足首）で返す。範囲外は clip される。

カスタム例（config.py で差し替え）::

  from mujoco_rl_sim.experiments.exp_002_2joint_a2c.warmup import WarmupContext

  def my_warmup(ctx: WarmupContext) -> tuple[float, float]:
    t = ctx.elapsed_s
    knee = 0.2 * t
    return (knee, 0.0)

  WARMUP_ACTION_FN = my_warmup
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from mujoco_rl_sim.experiments.exp_002_2joint_a2c.lib.ctrl import clip_policy_action

WarmupActionFn = Callable[["WarmupContext"], tuple[float, float]]


@dataclass(frozen=True, slots=True)
class WarmupContext:
  """ウォームアップ行動関数へ渡すコンテキスト。"""

  obs: Sequence[float]
  elapsed_s: float
  total_env_steps: int
  episode_step: int
  episode_index: int


def default_warmup_action(ctx: WarmupContext) -> tuple[float, float]:
  """既定: 直立付近の中立姿勢（必要ならこの関数を編集または差し替え）。"""
  _ = ctx
  return (0.0, 0.0)


def clip_warmup_action(action: tuple[float, float]) -> tuple[float, float]:
  return (
    clip_policy_action(action[0]),
    clip_policy_action(action[1]),
  )


def resolve_warmup_action(fn: WarmupActionFn, ctx: WarmupContext) -> tuple[float, float]:
  """fn(ctx) を呼び、ポリシーと同様 [-1, 1]² にクリップして返す。"""
  return clip_warmup_action(fn(ctx))
