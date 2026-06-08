"""報酬の静的ヘルパ（ゲート条件）の単体テスト。"""

from __future__ import annotations

import pytest

from sim.episode_state import BipedStepContext
from sim.env import EnvBipedPPO


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


@pytest.fixture
def reward(default_ctx):
  env = EnvBipedPPO(default_ctx, enable_viewer=False, training_dr_enabled=False)
  return env._reward


def test_aerial_duration_penalty_zero_when_foot_on_floor(reward) -> None:
  penalty = reward._aerial_duration_penalty(
    any_foot_on_floor=True,
    aerial_steps=999,
  )
  assert penalty == 0.0


def test_aerial_duration_penalty_after_threshold(reward, default_ctx) -> None:
  over = default_ctx.cfg.reward.aerial_duration_penalty_after_steps + 2
  penalty = reward._aerial_duration_penalty(
    any_foot_on_floor=False,
    aerial_steps=over,
  )
  assert penalty > 0.0


def test_alternating_landing_bonus_requires_flag(reward, default_ctx) -> None:
  off = reward._alternating_landing_bonus(biped=_biped_ctx(alternating_landing=False))
  on = reward._alternating_landing_bonus(biped=_biped_ctx(alternating_landing=True))
  assert off == 0.0
  assert on == default_ctx.cfg.reward.alternating_landing_bonus_scale


def test_double_support_penalty_only_when_both_feet_down(reward) -> None:
  none = reward._double_support_penalty(
    both_feet_on_floor=False,
    dx=0.1,
    left_foot_dx=0.1,
    right_foot_dx=0.1,
  )
  yes = reward._double_support_penalty(
    both_feet_on_floor=True,
    dx=0.1,
    left_foot_dx=0.1,
    right_foot_dx=0.1,
  )
  assert none == 0.0
  assert yes > 0.0
