"""eval 主指標の W&B / dispatch 用フラット化の単体テスト。"""

from __future__ import annotations

from rl.wandb_logging import _eval_summary_metrics


def test_eval_summary_metrics_from_report() -> None:
  report = {
    "primary_metric_name": "eval/displacement_x_mean",
    "primary_metric_value": 1.25,
    "summary": {
      "metrics": {
        "displacement_x": {"mean": 1.25, "std": 0.1, "ci95_low": 1.0, "ci95_high": 1.5},
        "truncated_rate": 0.2,
      }
    },
  }
  metrics = _eval_summary_metrics(report)
  assert metrics["eval/displacement_x_mean"] == 1.25
  assert metrics["eval/displacement_x_std"] == 0.1
  assert metrics["eval/truncated_rate"] == 0.2
