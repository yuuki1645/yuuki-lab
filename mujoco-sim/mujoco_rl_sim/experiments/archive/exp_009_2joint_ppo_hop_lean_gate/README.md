# exp_009: 片脚ホッパ PPO + 前傾ゲート・長エピソード

## exp_008 からの変更（仮説: 前傾ダイブで `imu_z` 終了）

| 項目 | exp_008 | exp_009 |
|------|---------|---------|
| 飛翔 IMU 前進 | 常時フルスケール | **前傾で減衰**（`FORWARD_IMU_LEAN_GATE`） |
| 前傾ペナルティ | 弱め | **強化**（閾値・スケール） |
| 長飛翔 | なし | **ステップペナルティ**（18 step 超） |
| 着地ボーナス | 0.4 | **0.55** |
| エピソード長 | 6 s | **30 s**（10 m 評価向け） |

観測・PPO・XML は exp_008 と同一（25 次元）。

## 途中打ち切り（2026-05-24）

- u2500 時点: seed 42 で **~2.0 m**（`low_upright` 終了）。残り +3000 updates は見込み薄のため停止。
- チェックポイント: `run_20260524_165804/update_002500.pt`

## 学習

```bash
python -m mujoco_rl_sim.experiments.archive.exp_009_2joint_ppo_hop_lean_gate.train
```

exp_008 から転移（任意）:

```bash
python -m mujoco_rl_sim.experiments.archive.exp_009_2joint_ppo_hop_lean_gate.train \
  --resume run_YYYYMMDD_HHMMSS/final.pt --lr 2e-4 --num-updates 4000
```

## ロールアウト分析

```bash
python -m mujoco_rl_sim.experiments.archive.exp_009_2joint_ppo_hop_lean_gate.analyze_rollout \
  --checkpoint run_YYYYMMDD_HHMMSS/latest.pt --seed 42
```
