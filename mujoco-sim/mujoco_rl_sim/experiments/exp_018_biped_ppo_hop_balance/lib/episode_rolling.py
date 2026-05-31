"""直近エピソードのローリング統計（学習ログ・wandb 用）。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class EpisodeSnapshot:
  return_: float
  length: float
  forward_reward_sum: float
  total_dx_imu: float
  net_imu_x: float


class EpisodeRollingWindow:
  """直近 window 本のエピソード指標を保持する。"""

  def __init__(self, *, window: int) -> None:
    if window < 1:
      raise ValueError("window は 1 以上")
    self._window = window
    self._episodes: deque[EpisodeSnapshot] = deque(maxlen=window)

  def push(
    self,
    *,
    return_: float,
    length: float,
    forward_reward_sum: float,
    total_dx_imu: float,
    net_imu_x: float,
  ) -> None:
    self._episodes.append(
      EpisodeSnapshot(
        return_=return_,
        length=length,
        forward_reward_sum=forward_reward_sum,
        total_dx_imu=total_dx_imu,
        net_imu_x=net_imu_x,
      )
    )

  def count(self) -> int:
    return len(self._episodes)

  def summary(self) -> dict[str, float] | None:
    if not self._episodes:
      return None
    eps = list(self._episodes)
    returns = [e.return_ for e in eps]
    lengths = [e.length for e in eps]
    forwards = [e.forward_reward_sum for e in eps]
    dx_sums = [e.total_dx_imu for e in eps]
    net_x = [e.net_imu_x for e in eps]
    return {
      "ep_roll_n": float(len(eps)),
      "ep_ret_mean": mean(returns),
      "ep_ret_max": max(returns),
      "ep_len_mean": mean(lengths),
      "ep_fwd_rw_mean": mean(forwards),
      "ep_dx_mean": mean(dx_sums),
      "ep_dx_max": max(dx_sums),
      "ep_net_x_mean": mean(net_x),
      "ep_net_x_max": max(net_x),
    }


def format_rolling_log_suffix(summary: dict[str, float] | None) -> str:
  """output.log 用の固定フォーマット suffix（パースしやすい）。"""
  if summary is None:
    return " | ep_roll_n:      0"
  return (
    f" | ep_roll_n: {int(summary['ep_roll_n']):6d}"
    f" | ep_ret_mean: {summary['ep_ret_mean']:10.5f}"
    f" | ep_ret_max: {summary['ep_ret_max']:10.5f}"
    f" | ep_len_mean: {summary['ep_len_mean']:10.3f}"
    f" | ep_fwd_rw_mean: {summary['ep_fwd_rw_mean']:10.5f}"
    f" | ep_dx_mean: {summary['ep_dx_mean']:10.5f}"
    f" | ep_dx_max: {summary['ep_dx_max']:10.5f}"
    f" | ep_net_x_mean: {summary['ep_net_x_mean']:10.5f}"
  )


def rolling_summary_to_wandb(summary: dict[str, float]) -> dict[str, float]:
  return {
    "train/ep_roll_n": summary["ep_roll_n"],
    "train/ep_return_mean": summary["ep_ret_mean"],
    "train/ep_return_max": summary["ep_ret_max"],
    "train/ep_length_mean": summary["ep_len_mean"],
    "train/ep_forward_reward_mean": summary["ep_fwd_rw_mean"],
    "train/ep_total_dx_imu_mean": summary["ep_dx_mean"],
    "train/ep_total_dx_imu_max": summary["ep_dx_max"],
    "train/ep_net_imu_x_mean": summary["ep_net_x_mean"],
    "train/ep_net_imu_x_max": summary["ep_net_x_max"],
  }
