"""dispatch_summary の主指標読み取り（eval 優先）。"""

from __future__ import annotations

from mujoco_rl_sim.dispatch.common.primary_metric import metric_from_summary_file


def test_prefers_eval_primary_metric() -> None:
  value = metric_from_summary_file(
    {
      "eval/displacement_x_mean": 1.25,
      "train/ep_return_mean_max": 99.0,
    }
  )
  assert value == 1.25


def test_falls_back_to_train_metric() -> None:
  value = metric_from_summary_file(
    {
      "train/ep_return_mean_max": 42.5,
    }
  )
  assert value == 42.5
