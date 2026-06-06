"""eval 集計ロジックの単体テスト。"""

from __future__ import annotations

from eval.metrics import EpisodeEvalRecord, summarize_episodes, summarize_values


def _record(*, displacement_x: float, trial_index: int = 0) -> EpisodeEvalRecord:
  return EpisodeEvalRecord(
    trial_index=trial_index,
    eval_seed=101,
    ep_index=0,
    displacement_x=displacement_x,
    origin_imu_x=0.0,
    final_imu_x=displacement_x,
    episode_length=100,
    truncated=False,
    termination_reason="truncated",
    alternating_landing_rate=0.5,
    single_support_ratio=0.6,
    double_support_ratio=0.1,
    episode_return=1.0,
    noise_applied={},
  )


def test_summarize_values_mean_and_ci() -> None:
  stats = summarize_values([1.0, 2.0, 3.0])
  assert stats["mean"] == 2.0
  assert stats["min"] == 1.0
  assert stats["max"] == 3.0
  assert stats["ci95_low"] <= stats["mean"] <= stats["ci95_high"]


def test_summarize_episodes_primary_metric() -> None:
  records = [_record(displacement_x=0.5), _record(displacement_x=1.5, trial_index=1)]
  summary = summarize_episodes(records)
  assert summary["primary_metric_value"] == 1.0
  assert summary["metrics"]["displacement_x"]["mean"] == 1.0
