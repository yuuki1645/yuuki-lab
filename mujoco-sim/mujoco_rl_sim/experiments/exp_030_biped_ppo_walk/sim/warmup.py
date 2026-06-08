"""各エピソード開始直後のウォームアップ行動（12 DOF、keyframe stand 相当）。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from lib.actuators import ACTUATOR_NAMES
from lib.ctrl import clip_policy_action
from lib.experiment_context import ExperimentContext, build_experiment_context
from conf.schema import build_app_config

WarmupActionFn = Callable[["WarmupContext"], tuple[float, ...]]


@dataclass(frozen=True, slots=True)
class WarmupContext:
  obs: Sequence[float]
  elapsed_s: float
  total_env_steps: int
  episode_step: int
  episode_index: int


_DEFAULT_CTX: ExperimentContext | None = None


def _resolve_ctx(ctx: ExperimentContext | None) -> ExperimentContext:
  global _DEFAULT_CTX
  if ctx is not None:
    return ctx
  if _DEFAULT_CTX is None:
    # 既存呼び出し互換: ctx 未指定なら既定 AppConfig から 1 回だけ生成する。
    _DEFAULT_CTX = build_experiment_context(build_app_config())
  return _DEFAULT_CTX


def episode_sim_elapsed_s(episode_step: int, ctx: ExperimentContext | None = None) -> float:
  resolved = _resolve_ctx(ctx)
  return episode_step * resolved.cfg.sim.control_timestep_s


def in_episode_warmup(episode_step: int, ctx: ExperimentContext | None = None) -> bool:
  """エピソード開始から WARMUP_DURATION_S 未満なら True（方策学習前の安定化期間）。"""
  resolved = _resolve_ctx(ctx)
  if not resolved.cfg.training.warmup_enabled:
    return False
  return episode_sim_elapsed_s(episode_step, resolved) < resolved.cfg.training.warmup_duration_s


def default_warmup_action(ctx: WarmupContext) -> tuple[float, ...]:
  """全関節 0 action（stand keyframe の中立 ctrl）。"""
  _ = ctx
  return (0.0,) * len(ACTUATOR_NAMES)


def clip_warmup_action(action: tuple[float, ...]) -> tuple[float, ...]:
  return tuple(clip_policy_action(a) for a in action)


def resolve_warmup_action(fn: WarmupActionFn, ctx: WarmupContext) -> tuple[float, ...]:
  return clip_warmup_action(fn(ctx))
