# exp_010: 進捗報酬 + 膝過屈曲ペナルティ + 足底摩擦

## exp_009 からの変更

| 項目 | exp_009 | exp_010 |
|------|---------|---------|
| 進捗報酬 | なし | **best_imu_x 更新分**（直立時） |
| 膝 | — | **飛翔中の過屈曲ペナルティ** |
| XML 足底 | 既定摩擦 | **friction 1.15** |
| 転移起点 | exp_008 u1500 | **同左**（exp_009 u2500 は ~2 m で打ち切り） |

## 長時間 run 打ち切り（2026-05-24）

- `run_20260524_180335`（+6000、u2460 付近）: u2000 評価 **~1.5 m** のため停止。
- 採用チェックポイント: **`run_20260524_173035/final.pt`（~3.1 m）** → exp_011 転移元。

## 学習

```bash
python -m mujoco_rl_sim.experiments.exp_010_2joint_ppo_hop_progress.train \
  --resume "../exp_008_2joint_ppo_hop_shaping/run_20260524_110357/update_001500.pt" \
  --lr 2e-4 --num-updates 2000
```

途中で `analyze_rollout` を見て見込みがなければ学習を止めて exp_011 へ。
