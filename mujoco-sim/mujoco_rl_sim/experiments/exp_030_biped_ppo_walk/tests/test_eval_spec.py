"""eval 試行計画の単体テスト。"""

from __future__ import annotations

from eval.spec import EPISODES_PER_SEED, EVAL_SEEDS, iter_eval_trials, make_episode_rng


def test_iter_eval_trials_count() -> None:
  plans = iter_eval_trials()
  assert len(plans) == len(EVAL_SEEDS) * EPISODES_PER_SEED


def test_make_episode_rng_is_deterministic() -> None:
  r1 = make_episode_rng(101, 0)
  r2 = make_episode_rng(101, 0)
  assert r1.random() == r2.random()
