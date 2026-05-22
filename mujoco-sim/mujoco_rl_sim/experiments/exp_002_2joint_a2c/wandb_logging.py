"""exp_002 用の任意 Weights & Biases ロギング。"""

from __future__ import annotations

import os
from collections import Counter, deque
from typing import Any

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.termination import (
  REASON_CONTACT_BASKET,
  REASON_CONTACT_SHANK,
  REASON_CONTACT_THIGH,
  TERMINATION_REASONS,
)

_active = False
_termination_tracker: TerminationTracker | None = None


class EpisodeMetricsCollector:
  """エピソード横断の wandb メトリクスを集計し、終了時に log する。"""

  def __init__(self) -> None:
    self.reset()

  def reset(self) -> None:
    self._return = 0.0
    self._forward = 0.0
    self._forward_imu = 0.0
    self._forward_foot = 0.0
    self._effort_penalty = 0.0
    self._upright_sum = 0.0
    self._foot_contact_steps = 0

  def on_step(self, reward: float, step_info: dict[str, Any]) -> None:
    if not _active:
      return
    self._return += reward
    self._forward += step_info["reward_forward"]
    self._forward_imu += step_info.get("reward_forward_imu", 0.0)
    self._forward_foot += step_info.get("reward_forward_foot", 0.0)
    self._effort_penalty += step_info["reward_effort_penalty"]
    self._upright_sum += step_info["upright"]
    self._foot_contact_steps += int(step_info["foot_on_floor"] > 0.5)

  def on_episode_end(
    self,
    *,
    episode_step: int,
    terminated: bool,
    truncated: bool,
    step_info: dict[str, Any],
    env_step: int,
  ) -> None:
    if not _active:
      return

    ep_len = float(episode_step)
    termination_reason = step_info.get("termination_reason")
    basket_force_n = step_info.get("basket_contact_normal_force_n")
    thigh_force_n = step_info.get("thigh_contact_normal_force_n")
    shank_force_n = step_info.get("shank_contact_normal_force_n")

    metrics: dict[str, float] = {
      "episode/return": self._return,
      "episode/length": ep_len,
      "episode/terminated": float(terminated),
      "episode/truncated": float(truncated and not terminated),
      "episode/mean_upright": self._upright_sum / ep_len,
      "episode/foot_contact_ratio": self._foot_contact_steps / ep_len,
      "episode/forward_reward_sum": self._forward,
      "episode/forward_imu_reward_sum": self._forward_imu,
      "episode/forward_foot_reward_sum": self._forward_foot,
      "episode/effort_penalty_sum": self._effort_penalty,
      "episode/contact_basket_penalty": float(
        step_info["reward_contact_basket_penalty"]
      ),
      "episode/contact_basket_normal_force_n": (
        float(basket_force_n) if basket_force_n is not None else 0.0
      ),
      "episode/contact_basket_terminated": float(
        termination_reason == REASON_CONTACT_BASKET
      ),
      "episode/contact_thigh_penalty": float(
        step_info["reward_contact_thigh_penalty"]
      ),
      "episode/contact_thigh_normal_force_n": (
        float(thigh_force_n) if thigh_force_n is not None else 0.0
      ),
      "episode/contact_thigh_terminated": float(
        termination_reason == REASON_CONTACT_THIGH
      ),
      "episode/contact_shank_penalty": float(
        step_info["reward_contact_shank_penalty"]
      ),
      "episode/contact_shank_normal_force_n": (
        float(shank_force_n) if shank_force_n is not None else 0.0
      ),
      "episode/contact_shank_terminated": float(
        termination_reason == REASON_CONTACT_SHANK
      ),
    }
    metrics.update(
      episode_termination_metrics(
        terminated=terminated,
        truncated=truncated,
        reason=termination_reason,
      )
    )
    log(metrics, step=env_step)
    self.reset()


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
    # truncated は env が reason を返さないため train 側のフラグから補完
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


def init(
  *,
  extra_config: dict[str, Any] | None = None,
  extra_tags: tuple[str, ...] | None = None,
  run_name: str | None = None,
) -> bool:
  """wandb.run を開始する。無効・未インストール時は False。

  extra_config / extra_tags / run_name は再開学習など別 run 用の上書き。
  """
  global _active, _termination_tracker
  if not is_enabled():
    return False

  try:
    import wandb
  except ImportError:
    print("[wandb] 未インストールです: pip install wandb  または USE_WANDB=False")
    return False

  run_config = config.training_config_dict()
  if extra_config:
    run_config.update(extra_config)

  tags = list(config.WANDB_TAGS)
  if extra_tags:
    tags.extend(extra_tags)

  init_kwargs: dict[str, Any] = {
    "project": config.WANDB_PROJECT,
    "config": run_config,
    "tags": tags,
  }
  name = run_name if run_name is not None else config.WANDB_RUN_NAME
  if name:
    init_kwargs["name"] = name
  if config.WANDB_ENTITY:
    init_kwargs["entity"] = config.WANDB_ENTITY

  wandb.init(**init_kwargs)
  _active = True
  _termination_tracker = TerminationTracker(
    rolling_window=config.WANDB_TERMINATION_ROLLING_WINDOW,
  )
  return True


def episode_collector() -> EpisodeMetricsCollector:
  """エピソード集計用 collector。wandb 無効時は on_step / on_episode_end が no-op。"""
  return EpisodeMetricsCollector()


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


def log_train_update(
  stats: dict[str, float],
  *,
  update: int,
  episodes_finished: int,
  step: int,
) -> None:
  """方策更新ごとの train/* メトリクスを log する。"""
  log(
    {
      "train/mean_target": stats["mean_target"],
      "train/policy_loss": stats["policy_loss"],
      "train/value_loss": stats["value_loss"],
      "train/entropy": stats["entropy"],
      "train/update": float(update),
      "train/episodes_finished": float(episodes_finished),
    },
    step=step,
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
