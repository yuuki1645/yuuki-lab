# exp_011: 直立・前傾ハードゲート + 進捗報酬強化

## exp_010 からの変更

| 項目 | exp_010 | exp_011 |
|------|---------|---------|
| 転移元 | exp_008 u1500 | **exp_010 final**（~3.1 m） |
| 飛翔 IMU 前進 | 前傾で減衰 | **前傾 >0.12 でゼロ** |
| 進捗報酬スケール | 12 | **30** |
| 飛翔低 upright | なし | **ペナルティ** |
| 着地 | 前傾上限のみ | **upright ≥ 0.72** も必須 |
| FORWARD_SCALE | 80 | **70** |

## 学習

```bash
python -m mujoco_rl_sim.experiments.exp_011_2joint_ppo_hop_upright_vel.train \
  --resume "../exp_010_2joint_ppo_hop_progress/run_20260524_173035/final.pt" \
  --lr 1.5e-4 --num-updates 2000
```

u500 / u1000 で `analyze_rollout --seed 42`。3 m 未満なら打ち切り → exp_012。
