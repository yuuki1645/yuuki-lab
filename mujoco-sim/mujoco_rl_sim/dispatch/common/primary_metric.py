"""主比較指標（eval / train）の定義。"""

from __future__ import annotations

# 学習中のローリング最大（従来の dispatch 主指標）
TRAIN_PRIMARY_METRIC_NAME = "train/ep_return_mean_max"
# exp_028/029 の Go/No-Go 基準（post-train eval 後はこちらを優先）
EVAL_PRIMARY_METRIC_NAME = "eval/displacement_x_mean"

# 後方互換エイリアス
PRIMARY_METRIC_NAME = TRAIN_PRIMARY_METRIC_NAME


def metric_from_summary_file(data: dict) -> float | None:
  """dispatch_summary.json から primary metric を読む。"""
  for key in (
    EVAL_PRIMARY_METRIC_NAME,
    TRAIN_PRIMARY_METRIC_NAME,
    "train/ep_return_mean",
    "episode/return",
  ):
    if key in data and data[key] is not None:
      try:
        return float(data[key])
      except (TypeError, ValueError):
        continue
  return None
