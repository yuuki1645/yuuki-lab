"""学習ループのスループット計測（rollout vs PPO update の壁時計時間）。

レベル1: ボトルネック特定用。``contract/session.py`` が update ごとに記録し、
コンソール / W&B に ``rollout_fraction`` と ``steps_per_sec`` を出す。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateTiming:
  """1 回の PPO update にかかった壁時計時間 [s]。"""

  rollout_s: float
  ppo_update_s: float
  rollout_steps: int
  ipc_s: float = 0.0
  act_batch_s: float = 0.0
  num_envs: int = 1

  @property
  def total_s(self) -> float:
    return self.rollout_s + self.ppo_update_s

  @property
  def rollout_fraction(self) -> float:
    """rollout が update 全体に占める割合（0〜1）。高いほど sim 側が支配的。"""
    total = self.total_s
    if total <= 0.0:
      return 0.0
    return float(self.rollout_s / total)

  @property
  def steps_per_sec(self) -> float:
    """ロールアウト収集中の環境ステップ / 秒。"""
    if self.rollout_s <= 0.0:
      return 0.0
    return float(self.rollout_steps / self.rollout_s)


@dataclass
class ThroughputTracker:
  """run 全体の累積スループット統計。"""

  rollout_steps_per_update: int
  update_count: int = 0
  sum_rollout_s: float = 0.0
  sum_ppo_update_s: float = 0.0
  sum_total_s: float = 0.0

  def record(self, timing: UpdateTiming) -> None:
    self.update_count += 1
    self.sum_rollout_s += timing.rollout_s
    self.sum_ppo_update_s += timing.ppo_update_s
    self.sum_total_s += timing.total_s

  @property
  def avg_update_s(self) -> float:
    if self.update_count <= 0:
      return 0.0
    return self.sum_total_s / self.update_count

  @property
  def avg_rollout_fraction(self) -> float:
    if self.sum_total_s <= 0.0:
      return 0.0
    return float(self.sum_rollout_s / self.sum_total_s)

  @property
  def avg_steps_per_sec(self) -> float:
    if self.sum_rollout_s <= 0.0:
      return 0.0
    total_steps = self.rollout_steps_per_update * self.update_count
    return float(total_steps / self.sum_rollout_s)

  def wandb_metrics(self, timing: UpdateTiming) -> dict[str, float]:
    """W&B 用の平坦な指標 dict（この update + 累積平均）。"""
    return {
      "train/update_wall_s": timing.total_s,
      "train/rollout_wall_s": timing.rollout_s,
      "train/ppo_update_wall_s": timing.ppo_update_s,
      "train/rollout_fraction": timing.rollout_fraction,
      "train/steps_per_sec": timing.steps_per_sec,
      "train/avg_update_wall_s": self.avg_update_s,
      "train/avg_rollout_fraction": self.avg_rollout_fraction,
      "train/avg_steps_per_sec": self.avg_steps_per_sec,
      "train/ipc_wall_s": timing.ipc_s,
      "train/act_batch_wall_s": timing.act_batch_s,
      "train/num_envs": float(timing.num_envs),
    }

  def format_interval_suffix(self, timing: UpdateTiming) -> str:
    """コンソール 1 行ログ用の追加サフィックス。"""
    suffix = (
      f" | rollout_s: {timing.rollout_s:7.3f}"
      f" ppo_s: {timing.ppo_update_s:6.3f}"
      f" | rollout_frac: {timing.rollout_fraction:4.2f}"
      f" | steps/s: {timing.steps_per_sec:6.1f}"
    )
    if timing.num_envs > 1:
      suffix += (
        f" | num_envs: {timing.num_envs}"
        f" ipc_s: {timing.ipc_s:6.3f}"
      )
    return suffix

  def format_run_summary(self) -> str:
    """学習 run 終了時のサマリ 1 行。"""
    if self.update_count <= 0:
      return "[throughput] no updates recorded"
    return (
      f"[throughput] updates={self.update_count} "
      f"avg_update_s={self.avg_update_s:.3f} "
      f"avg_rollout_frac={self.avg_rollout_fraction:.2f} "
      f"avg_steps/s={self.avg_steps_per_sec:.1f}"
    )


def pacing_warnings(
  *,
  viewer: bool,
  telemetry: bool,
  step_wall_sleep_sec: float,
  num_envs: int = 1,
) -> list[str]:
  """学習スループットを落とす設定が有効なときの警告メッセージ。"""
  warnings: list[str] = []
  if viewer:
    warnings.append(
      "[throughput] viewer enabled → use --no-viewer for max collection speed"
    )
  if telemetry:
    warnings.append(
      "[throughput] telemetry enabled → use --no-telemetry for max collection speed"
    )
  if step_wall_sleep_sec > 0.0:
    warnings.append(
      f"[throughput] step_wall_sleep={step_wall_sleep_sec:g}s "
      "→ use --step-wall-sleep 0 for max collection speed"
    )
  if num_envs > 1 and viewer:
    warnings.append(
      "[throughput] subproc vec env does not support viewer; use --no-viewer"
    )
  if num_envs > 1 and telemetry:
    warnings.append(
      "[throughput] subproc vec env does not support telemetry; use --no-telemetry"
    )
  return warnings
