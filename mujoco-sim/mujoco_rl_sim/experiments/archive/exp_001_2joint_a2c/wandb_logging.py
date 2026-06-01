"""exp_001 用の任意 Weights & Biases ロギング。"""

from __future__ import annotations

import os
from collections import Counter, deque
from typing import Any

import config
from termination import TERMINATION_REASONS

_active = False
_termination_tracker: TerminationTracker | None = None


class TerminationTracker:
  """エピソード終了理由の累積・比率・直近ウィンドウを集計する。"""

  def __init__(self, *, rolling_window: int) -> None:
    self._rolling_window = rolling_window
    self._counts = {reason: 0 for reason in TERMINATION_REASONS}
    self._total = 0
    self._recent: deque[str] = deque(maxlen=rolling_window)

  def record(
    self,
    *,
    terminated: bool,
    truncated: bool,
    reason: str | None,
  ) -> dict[str, float]:
    if truncated and not terminated:
      key = "truncated"
    elif reason in TERMINATION_REASONS:
      key = reason
    else:
      return {}

    self._counts[key] += 1
    self._total += 1
    self._recent.append(key)

    metrics: dict[str, float] = {}
    for reason_name in TERMINATION_REASONS:
      count = self._counts[reason_name]
      metrics[f"termination/cumulative_{reason_name}"] = float(count)
      metrics[f"termination/rate_{reason_name}"] = count / self._total
      metrics[f"episode/terminate_{reason_name}"] = 1.0 if key == reason_name else 0.0

    recent_counts = Counter(self._recent)
    recent_total = len(self._recent)
    for reason_name in TERMINATION_REASONS:
      metrics[f"termination/rolling_rate_{reason_name}"] = (
        recent_counts[reason_name] / recent_total
      )

    dominant = max(TERMINATION_REASONS, key=lambda r: self._counts[r])
    for reason_name in TERMINATION_REASONS:
      metrics[f"termination/is_dominant_{reason_name}"] = (
        1.0 if reason_name == dominant else 0.0
      )

    return metrics


def is_enabled() -> bool:
  if not config.USE_WANDB:
    return False
  if os.environ.get("WANDB_MODE", "").lower() == "disabled":
    return False
  return True


def init() -> bool:
  """wandb.run を開始する。無効・未インストール時は False。"""
  global _active, _termination_tracker
  if not is_enabled():
    return False

  try:
    import wandb
  except ImportError:
    print("[wandb] 未インストールです: pip install wandb  または USE_WANDB=False")
    return False

  init_kwargs: dict[str, Any] = {
    "project": config.WANDB_PROJECT,
    "config": config.training_config_dict(),
    "tags": list(config.WANDB_TAGS),
  }
  if config.WANDB_RUN_NAME:
    init_kwargs["name"] = config.WANDB_RUN_NAME
  if config.WANDB_ENTITY:
    init_kwargs["entity"] = config.WANDB_ENTITY

  wandb.init(**init_kwargs)
  _active = True
  _termination_tracker = TerminationTracker(
    rolling_window=config.WANDB_TERMINATION_ROLLING_WINDOW,
  )
  return True


def episode_termination_metrics(
  *,
  terminated: bool,
  truncated: bool,
  reason: str | None,
) -> dict[str, float]:
  """エピソード終了時に wandb.log へ足す終了理由メトリクス。"""
  if _termination_tracker is None:
    return {}
  return _termination_tracker.record(
    terminated=terminated,
    truncated=truncated,
    reason=reason,
  )


def log(metrics: dict[str, float], *, step: int) -> None:
  if not _active:
    return
  import wandb

  wandb.log(metrics, step=step)


def finish() -> None:
  global _active, _termination_tracker
  if not _active:
    return
  import wandb

  wandb.finish()
  _active = False
  _termination_tracker = None
