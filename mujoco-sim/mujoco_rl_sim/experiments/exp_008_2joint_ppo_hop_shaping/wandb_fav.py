"""wandb 用 fav/* エイリアス（ワークスペース別セクション用）。"""

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
