"""報酬の静的ヘルパ（ゲート条件）の単体テスト。"""

from __future__ import annotations

import config
from sim.episode_state import BipedStepContext
from sim.reward import Reward


def _biped_ctx(**kwargs) -> BipedStepContext:
  defaults = dict(
    left_landed=False,
    right_landed=False,
    aerial_steps=0,
    both_feet_on_floor=False,
    any_foot_on_floor=True,
    single_support=True,
    single_support_side=1,
    alternating_landing=False,
  )
  defaults.update(kwargs)
  return BipedStepContext(**defaults)


def test_aerial_duration_penalty_zero_when_foot_on_floor() -> None:
  penalty = Reward._aerial_duration_penalty(
    any_foot_on_floor=True,
    aerial_steps=999,
  )
  assert penalty == 0.0


def test_aerial_duration_penalty_after_threshold() -> None:
  over = config.AERIAL_DURATION_PENALTY_AFTER_STEPS + 2
  penalty = Reward._aerial_duration_penalty(
    any_foot_on_floor=False,
    aerial_steps=over,
  )
  assert penalty > 0.0


def test_alternating_landing_bonus_requires_flag() -> None:
  off = Reward._alternating_landing_bonus(biped=_biped_ctx(alternating_landing=False))
  on = Reward._alternating_landing_bonus(biped=_biped_ctx(alternating_landing=True))
  assert off == 0.0
  assert on == config.ALTERNATING_LANDING_BONUS_SCALE


def test_double_support_penalty_only_when_both_feet_down() -> None:
  none = Reward._double_support_penalty(
    both_feet_on_floor=False,
    dx=0.1,
    left_foot_dx=0.1,
    right_foot_dx=0.1,
  )
  yes = Reward._double_support_penalty(
    both_feet_on_floor=True,
    dx=0.1,
    left_foot_dx=0.1,
    right_foot_dx=0.1,
  )
  assert none == 0.0
  # ペナルティ項は正のスカラー（合成時に減算される）
  assert yes > 0.0
