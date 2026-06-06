# exp_014: マイルストーン + 生存ボーナス + 姿勢終了緩和

## exp_010 からの変更

| 項目 | exp_010 | exp_014 |
|------|---------|---------|
| マイルストーン | なし | `(1.0, 2.5, 4.0, 6.0, 8.0, 10.0) m` 通過ごとに `+5.0` |
| 生存ボーナス | なし | **`SURVIVAL_BONUS_SCALE=0.12`**（直立・高さ条件付き） |
| 進捗報酬 | `PROGRESS_REWARD_SCALE=20.0` | **`22.0`** |
| push/landing | exp_010 同等 | **係数を弱める**（`PUSH_OFF=0.25`, `LANDING=0.55`） |
| 姿勢終了 | exp_010 同等 | **さらに緩和**（`MIN_IMU_Z=0.37`, `MIN_IMU_UPRIGHT=0.50`） |

## 背景

exp_010 ベスト（~3.1 m）から 10 m 直達のスパース報酬と早期終了緩和を試行。

## 学習

```bash
cd mujoco-sim/mujoco_rl_sim/experiments/archive/exp_014_2joint_ppo_hop_milestone_pose
python train.py \
  --resume "../archive/exp_010_2joint_ppo_hop_progress/run_20260524_173035/final.pt" \
  --lr 2e-4 --num-updates 2000
```

チェックポイント: `mujoco_rl_sim/runs/archive/exp_014_2joint_ppo_hop_milestone_pose/run_YYYYMMDD_HHMMSS/`

## 観測・制御

- 観測 **25 次元** / 行動 **2 次元**（exp_010 と同一）
- 制御 **50 Hz**（`FRAME_SKIP=10`）
