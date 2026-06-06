# exp_013: 累積距離マイルストーン報酬

## exp_010 からの変更

| 項目 | exp_010 | exp_013 |
|------|---------|---------|
| 進捗報酬 | `best_imu_x` 更新分 | **同一**（`PROGRESS_REWARD_SCALE=20.0`） |
| マイルストーン | なし | **累積 IMU X 距離** `(1.0, 2.0, 3.5, 5.0, 7.5, 10.0) m` 通過ごとに `+4.0` |
| 姿勢終了 | exp_010 同等 | **やや緩和**（`MIN_IMU_Z=0.39`, `MIN_IMU_UPRIGHT=0.52`） |
| 転移起点 | exp_008 u1500 | **exp_010 final**（~3.1 m） |

## 背景

exp_010 final が現状ベスト（~3.1 m）。10 m を明示的スパース報酬で狙う。

## 学習

```bash
cd mujoco-sim/mujoco_rl_sim/experiments/archive/exp_013_2joint_ppo_hop_milestones
python train.py \
  --resume "../archive/exp_010_2joint_ppo_hop_progress/run_20260524_173035/final.pt" \
  --lr 2e-4 --num-updates 2000
```

チェックポイント: `mujoco_rl_sim/runs/archive/exp_013_2joint_ppo_hop_milestones/run_YYYYMMDD_HHMMSS/`

## 観測・制御

- 観測 **25 次元** / 行動 **2 次元**（exp_010 と同一）
- 制御 **50 Hz**（`FRAME_SKIP=10`）
