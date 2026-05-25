"""各エピソード開始直後のウォームアップ行動（10 DOF、keyframe stand 相当）。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from . import config
from .lib.actuators import ACTUATOR_NAMES
from .lib.ctrl import clip_policy_action

WarmupActionFn = Callable[["WarmupContext"], tuple[float, ...]]


@dataclass(frozen=True, slots=True)
class WarmupContext:
  obs: Sequence[float]
  elapsed_s: float
  total_env_steps: int
  episode_step: int
  episode_index: int


def episode_sim_elapsed_s(episode_step: int) -> float:
  return episode_step * config.CONTROL_TIMESTEP_S


def in_episode_warmup(episode_step: int) -> bool:
  if not config.WARMUP_ENABLED:
    return False
  return episode_sim_elapsed_s(episode_step) < config.WARMUP_DURATION_S


def default_warmup_action(ctx: WarmupContext) -> tuple[float, ...]:
  """全関節 0 action（stand keyframe の中立 ctrl）。"""
  _ = ctx
  return (0.0,) * len(ACTUATOR_NAMES)


def clip_warmup_action(action: tuple[float, ...]) -> tuple[float, ...]:
  return tuple(clip_policy_action(a) for a in action)


def resolve_warmup_action(fn: WarmupActionFn, ctx: WarmupContext) -> tuple[float, ...]:
  return clip_warmup_action(fn(ctx))
