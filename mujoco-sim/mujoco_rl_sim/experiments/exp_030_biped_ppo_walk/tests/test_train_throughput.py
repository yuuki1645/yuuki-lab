"""スループット計測ヘルパの単体テスト。"""

from __future__ import annotations

from lib.train_throughput import ThroughputTracker, UpdateTiming, pacing_warnings


def test_update_timing_rollout_fraction() -> None:
  timing = UpdateTiming(rollout_s=8.0, ppo_update_s=2.0, rollout_steps=512)
  assert timing.total_s == 10.0
  assert timing.rollout_fraction == 0.8
  assert timing.steps_per_sec == 64.0


def test_throughput_tracker_averages() -> None:
  tracker = ThroughputTracker(rollout_steps_per_update=512)
  tracker.record(UpdateTiming(rollout_s=10.0, ppo_update_s=0.0, rollout_steps=512))
  tracker.record(UpdateTiming(rollout_s=5.0, ppo_update_s=5.0, rollout_steps=512))
  assert tracker.update_count == 2
  assert tracker.avg_update_s == 10.0
  assert tracker.avg_rollout_fraction == 0.75
  assert tracker.avg_steps_per_sec == 512 / 7.5


def test_pacing_warnings_lists_slow_settings() -> None:
  msgs = pacing_warnings(viewer=True, telemetry=True, step_wall_sleep_sec=0.02)
  assert len(msgs) == 3
