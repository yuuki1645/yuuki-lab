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


def _episode_batch_summary(eps: list[EpisodeSnapshot]) -> dict[str, float]:
  """エピソードリストから平均・最大を算出（rolling / interval 共通）。"""
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


class EpisodeRollingWindow:
  """直近 window 本のエピソード指標を保持する（wandb 用）。"""

  def __init__(self, *, window: int) -> None:
    if window < 1:
      raise ValueError("window は 1 以上")
    self._window = window
    self._episodes: deque[EpisodeSnapshot] = deque(maxlen=window)

  def push(self, snapshot: EpisodeSnapshot) -> None:
    self._episodes.append(snapshot)

  def count(self) -> int:
    return len(self._episodes)

  def summary(self) -> dict[str, float] | None:
    if not self._episodes:
      return None
    return _episode_batch_summary(list(self._episodes))


class EpisodeIntervalBuffer:
  """前回コンソールログ以降に終了したエピソードを保持する。"""

  def __init__(self) -> None:
    self._episodes: list[EpisodeSnapshot] = []

  def push(self, snapshot: EpisodeSnapshot) -> None:
    self._episodes.append(snapshot)

  def take_summary(self) -> dict[str, float] | None:
    """集計してバッファを空にする（ログ 1 行 = 前回ログから今回まで）。"""
    if not self._episodes:
      return None
    summary = _episode_batch_summary(self._episodes)
    self._episodes.clear()
    return summary


def format_interval_log_suffix(summary: dict[str, float] | None) -> str:
  """前回ログ区間のエピソード統計（コンソール進捗行用）。"""
  if summary is None:
    return (
      " | ep_ret_mean:        n/a"
      " | ep_len_mean:        n/a"
      " | ep_fwd_rw_mean:        n/a"
      " | ep_dx_mean:        n/a"
      " | ep_dx_max:        n/a"
      " | ep_net_x_mean:        n/a"
    )
  return (
    f" | ep_ret_mean: {summary['ep_ret_mean']:7.1f}"
    f" | ep_len_mean: {summary['ep_len_mean']:7.1f}"
    f" | ep_fwd_rw_mean: {summary['ep_fwd_rw_mean']:7.1f}"
    f" | ep_dx_mean: {summary['ep_dx_mean']:7.1f}"
    f" | ep_dx_max: {summary['ep_dx_max']:7.1f}"
    f" | ep_net_x_mean: {summary['ep_net_x_mean']:10.3f}"
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
