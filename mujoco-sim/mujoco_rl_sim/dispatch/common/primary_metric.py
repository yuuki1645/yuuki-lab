"""主比較指標（episode/return 系）の定義。"""

from __future__ import annotations

PRIMARY_METRIC_NAME = "train/ep_return_mean_max"


def metric_from_summary_file(data: dict) -> float | None:
  """dispatch_summary.json から primary metric を読む。"""
  for key in (PRIMARY_METRIC_NAME, "train/ep_return_mean", "episode/return"):
    if key in data and data[key] is not None:
      try:
        return float(data[key])
      except (TypeError, ValueError):
        continue
  return None
