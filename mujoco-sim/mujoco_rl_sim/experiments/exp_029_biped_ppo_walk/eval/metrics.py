"""Eval 指標の集計（mean / std / min / max / 95%CI）。"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from eval.spec import PRIMARY_METRIC_NAME

# 両側 95%・自由度 df に対する t 臨界値（scipy 非依存・df=1..30）
_T_CRIT_95: tuple[float, ...] = (
  0.0,
  12.706,
  4.303,
  3.182,
  2.776,
  2.571,
  2.447,
  2.365,
  2.306,
  2.262,
  2.228,
  2.201,
  2.179,
  2.160,
  2.145,
  2.131,
  2.120,
  2.110,
  2.101,
  2.093,
  2.086,
  2.080,
  2.074,
  2.069,
  2.064,
  2.060,
  2.056,
  2.052,
  2.048,
  2.045,
  2.042,
)


@dataclass(frozen=True)
class EpisodeEvalRecord:
  """1 試行分の評価結果。"""

  trial_index: int
  eval_seed: int
  ep_index: int
  displacement_x: float
  origin_imu_x: float
  final_imu_x: float
  episode_length: int
  truncated: bool
  termination_reason: str
  alternating_landing_rate: float
  single_support_ratio: float
  double_support_ratio: float
  episode_return: float
  noise_applied: dict[str, Any]


def _t_critical_95(sample_size: int) -> float:
  df = max(1, int(sample_size) - 1)
  if df >= len(_T_CRIT_95):
    return 2.0
  return float(_T_CRIT_95[df])


def summarize_values(values: Sequence[float]) -> dict[str, float]:
  """スカラー列の記述統計と 95%CI（平均の CI）。"""
  arr = np.asarray(values, dtype=np.float64)
  n = int(arr.size)
  if n == 0:
    return {
      "mean": 0.0,
      "std": 0.0,
      "min": 0.0,
      "max": 0.0,
      "ci95_low": 0.0,
      "ci95_high": 0.0,
      "n": 0.0,
    }

  mean = float(np.mean(arr))
  if n == 1:
    std = 0.0
    ci_low = mean
    ci_high = mean
  else:
    std = float(np.std(arr, ddof=1))
    sem = std / math.sqrt(n)
    half = _t_critical_95(n) * sem
    ci_low = mean - half
    ci_high = mean + half

  return {
    "mean": mean,
    "std": std,
    "min": float(np.min(arr)),
    "max": float(np.max(arr)),
    "ci95_low": float(ci_low),
    "ci95_high": float(ci_high),
    "n": float(n),
  }


def summarize_episodes(records: Sequence[EpisodeEvalRecord]) -> dict[str, Any]:
  """全試行の primary / secondary 集計。"""
  displacement = [r.displacement_x for r in records]
  episode_lengths = [float(r.episode_length) for r in records]
  alternating_rates = [r.alternating_landing_rate for r in records]
  single_support = [r.single_support_ratio for r in records]
  double_support = [r.double_support_ratio for r in records]

  truncated_count = sum(1 for r in records if r.truncated)
  n = len(records)
  reason_counter = Counter(r.termination_reason for r in records)

  disp_stats = summarize_values(displacement)

  return {
    "primary_metric_name": PRIMARY_METRIC_NAME,
    "primary_metric_value": disp_stats["mean"],
    "metrics": {
      "displacement_x": disp_stats,
      "episode_length": summarize_values(episode_lengths),
      "alternating_landing_rate": summarize_values(alternating_rates),
      "single_support_ratio": summarize_values(single_support),
      "double_support_ratio": summarize_values(double_support),
      "truncated_rate": float(truncated_count / n) if n else 0.0,
      "termination_breakdown": {k: int(v) for k, v in sorted(reason_counter.items())},
    },
  }


def episode_to_dict(record: EpisodeEvalRecord) -> dict[str, Any]:
  """per-episode JSON 用。"""
  return {
    "trial_index": record.trial_index,
    "eval_seed": record.eval_seed,
    "ep_index": record.ep_index,
    "displacement_x": record.displacement_x,
    "origin_imu_x": record.origin_imu_x,
    "final_imu_x": record.final_imu_x,
    "episode_length": record.episode_length,
    "truncated": record.truncated,
    "termination_reason": record.termination_reason,
    "alternating_landing_rate": record.alternating_landing_rate,
    "single_support_ratio": record.single_support_ratio,
    "double_support_ratio": record.double_support_ratio,
    "episode_return": record.episode_return,
    "noise_applied": record.noise_applied,
  }
