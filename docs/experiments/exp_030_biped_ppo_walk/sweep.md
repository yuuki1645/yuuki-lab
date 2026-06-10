# exp_030 — sweep

**AWS（推奨）**: `python scripts/aws_launch.py --sweep sweeps/walk_reward_sweep_48.yaml --confirm`（`param_grid` 付き YAML は v0 未対応。seed 列のみの YAML を使用）。  
詳細: [aws/README.md](../../../mujoco-sim/aws/README.md)。

**LAN レガシー（dispatch）**:

```bash
python -m mujoco_rl_sim.dispatch.coordinator.cli plan --file sweeps/walk_reward_sweep_48.yaml
```

| 探索軸 | 値 | 意図 |
|--------|-----|------|
| `double_support_penalty_scale` | 4, 8, 14 | すり足抑制の強さ |
| `alternating_landing_bonus_scale` | 0.25, 0.55 | 左右交互着地 |
| `forward_reward_scale` | 40, 55 | 前進 vs shaping のバランス |
| seed | 1–4 | 12 設定 × 4 = **48 job** |

LR は `ppo.lr=2.5e-4` 固定（`conf/ppo/default.yaml`、MLP 拡大時の exp_026 既定）。
