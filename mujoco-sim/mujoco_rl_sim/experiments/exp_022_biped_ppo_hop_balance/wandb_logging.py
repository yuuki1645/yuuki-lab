"""exp_008 用の任意 Weights & Biases ロギング。"""

from __future__ import annotations

import os
from collections import Counter, deque
from pathlib import Path
from typing import Any

from lib.episode_rolling import (
  EpisodeRollingWindow,
  format_rolling_log_suffix,
  rolling_summary_to_wandb,
)
from lib.run_dir import wandb_active_run_name

import config
from termination import (
  REASON_BACKWARD_LEAN,
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  TERMINATION_REASONS,
)

# wandb UI の fav/* セクション用エイリアス
FAV_METRIC_ALIASES: dict[str, str] = {
  "train/update": "fav/update",
  "episode/return": "fav/return",
  "episode/length": "fav/length",
  "episode/forward_reward_sum": "fav/forward_reward_sum",
  "episode/total_dx_imu": "fav/total_dx_imu",
  "train/ep_return_mean": "fav/ep_return_mean",
  "train/ep_total_dx_imu_mean": "fav/ep_total_dx_imu_mean",
}


def with_fav_metrics(metrics: dict[str, float]) -> dict[str, float]:
  """主要メトリクスを fav/* に複製して返す。"""
  out = dict(metrics)
  for src, dst in FAV_METRIC_ALIASES.items():
    if src in metrics:
      out[dst] = metrics[src]
  return out


_active = False
_termination_tracker: TerminationTracker | None = None


class EpisodeMetricsCollector:
  def __init__(self) -> None:
    self._rolling = EpisodeRollingWindow(window=config.EPISODE_ROLLING_WINDOW)
    self.reset()

  def reset(self) -> None:
    self._return = 0.0
    self._forward = 0.0
    self._episode_dx_sum = 0.0
    self._episode_start_imu_x: float | None = None
    self._policy_steps_in_episode = 0
    self._forward_imu = 0.0
    self._forward_foot = 0.0
    self._effort_penalty = 0.0
    self._shaping = 0.0
    self._upright_bonus = 0.0
    self._push_off_bonus = 0.0
    self._landing_bonus = 0.0
    self._backward_lean_penalty = 0.0
    self._forward_lean_penalty = 0.0
    self._height_penalty = 0.0
    self._flight_duration_penalty = 0.0
    self._upright_sum = 0.0
    self._stance_steps = 0
    self._entered_stance_steps = 0
    self._max_flight_steps = 0

  def on_step(self, reward: float, step_info: dict[str, Any]) -> None:
    self._policy_steps_in_episode += 1
    self._episode_dx_sum += float(step_info.get("imu_dx", 0.0))
    if self._episode_start_imu_x is None:
      self._episode_start_imu_x = float(step_info.get("imu_x", 0.0))
    if not _active:
      return
    self._return += reward
    self._forward += step_info["reward_forward"]
    self._forward_imu += step_info.get("reward_forward_imu", 0.0)
    self._forward_foot += step_info.get("reward_forward_foot", 0.0)
    self._effort_penalty += step_info["reward_effort_penalty"]
    self._shaping += step_info.get("reward_shaping", 0.0)
    self._upright_bonus += step_info.get("reward_upright", 0.0)
    self._push_off_bonus += step_info.get("reward_push_off", 0.0)
    self._landing_bonus += step_info.get("reward_landing", 0.0)
    self._backward_lean_penalty += step_info.get("reward_backward_lean_penalty", 0.0)
    self._forward_lean_penalty += step_info.get("reward_forward_lean_penalty", 0.0)
    self._height_penalty += step_info.get("reward_height_penalty", 0.0)
    self._flight_duration_penalty += step_info.get(
      "reward_flight_duration_penalty", 0.0
    )
    self._upright_sum += step_info["upright"]
    self._stance_steps += int(step_info.get("in_stance", 0.0) > 0.5)
    self._entered_stance_steps += int(step_info.get("entered_stance", 0.0) > 0.5)
    flight = int(step_info.get("flight_steps", 0.0))
    self._max_flight_steps = max(self._max_flight_steps, flight)

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

    end_imu_x = float(step_info.get("imu_x", 0.0))
    start_imu_x = (
      self._episode_start_imu_x
      if self._episode_start_imu_x is not None
      else end_imu_x
    )
    net_imu_x = end_imu_x - start_imu_x
    total_dx_imu = self._episode_dx_sum

    if self._policy_steps_in_episode > 0:
      self._rolling.push(
        return_=self._return,
        length=ep_len,
        forward_reward_sum=self._forward,
        total_dx_imu=total_dx_imu,
        net_imu_x=net_imu_x,
      )

    metrics: dict[str, float] = {
      "episode/return": self._return,
      "episode/length": ep_len,
      "episode/total_dx_imu": total_dx_imu,
      "episode/net_imu_x": net_imu_x,
      "episode/terminated": float(terminated),
      "episode/truncated": float(truncated and not terminated),
      "episode/mean_upright": self._upright_sum / ep_len,
      "episode/stance_ratio": self._stance_steps / ep_len,
      "episode/entered_stance_count": float(self._entered_stance_steps),
      "episode/max_flight_steps": float(self._max_flight_steps),
      "episode/forward_reward_sum": self._forward,
      "episode/forward_imu_reward_sum": self._forward_imu,
      "episode/forward_foot_reward_sum": self._forward_foot,
      "episode/effort_penalty_sum": self._effort_penalty,
      "episode/shaping_sum": self._shaping,
      "episode/upright_bonus_sum": self._upright_bonus,
      "episode/push_off_bonus_sum": self._push_off_bonus,
      "episode/landing_bonus_sum": self._landing_bonus,
      "episode/backward_lean_penalty_sum": self._backward_lean_penalty,
      "episode/forward_lean_penalty_sum": self._forward_lean_penalty,
      "episode/height_penalty_sum": self._height_penalty,
      "episode/flight_duration_penalty_sum": self._flight_duration_penalty,
      "episode/pose_penalty": float(step_info.get("reward_pose_penalty", 0.0)),
      "episode/pose_terminated": float(
        termination_reason
        in (REASON_IMU_Z, REASON_LOW_UPRIGHT, REASON_BACKWARD_LEAN)
      ),
      "episode/terminate_imu_z": float(termination_reason == REASON_IMU_Z),
      "episode/terminate_low_upright": float(
        termination_reason == REASON_LOW_UPRIGHT
      ),
      "episode/terminate_backward_lean": float(
        termination_reason == REASON_BACKWARD_LEAN
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

  def rolling_summary(self) -> dict[str, float] | None:
    return self._rolling.summary()

  def format_rolling_log_suffix(self) -> str:
    return format_rolling_log_suffix(self._rolling.summary())


class TerminationTracker:
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


def init(
  *,
  extra_config: dict[str, Any] | None = None,
  extra_tags: tuple[str, ...] | None = None,
  run_name: str | None = None,
  enabled: bool = True,
) -> bool:
  global _active, _termination_tracker
  if not enabled:
    print("[wandb] disabled")
    return False
  if os.environ.get("WANDB_MODE", "").lower() == "disabled":
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
  return EpisodeMetricsCollector()


def episode_termination_metrics(
  *,
  terminated: bool,
  truncated: bool,
  reason: str | None,
) -> dict[str, float]:
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
  episode_rolling: dict[str, float] | None = None,
) -> None:
  metrics: dict[str, float] = {
    "train/mean_target": stats["mean_target"],
    "train/policy_loss": stats["policy_loss"],
    "train/value_loss": stats["value_loss"],
    "train/entropy": stats["entropy"],
    "train/approx_kl": stats.get("approx_kl", float("nan")),
    "train/clip_fraction": stats.get("clip_fraction", float("nan")),
    "train/update": float(update),
    "train/episodes_finished": float(episodes_finished),
  }
  if episode_rolling is not None:
    metrics.update(rolling_summary_to_wandb(episode_rolling))

  if not _active:
    return
  import wandb
  wandb.log(with_fav_metrics(metrics), step=step)


def log(metrics: dict[str, float], *, step: int) -> None:
  if not _active:
    return
  import wandb

  wandb.log(with_fav_metrics(metrics), step=step)


def active_run_name() -> str | None:
  """有効な wandb run の Name（チェックポイント run ディレクトリ名に使用）。"""
  if not _active:
    return None
  return wandb_active_run_name()


def log_checkpoint_run_dir(path: Path) -> None:
  """ローカルチェックポイント run パスを wandb config に記録する。"""
  if not _active:
    return
  import wandb

  if wandb.run is None:
    return
  wandb.config.update({"checkpoint_run_dir": str(path)}, allow_val_change=True)


def finish() -> None:
  global _active, _termination_tracker
  if not _active:
    return
  import wandb

  wandb.finish()
  _active = False
  _termination_tracker = None
