# exp_007a: 前進報酬の足底接地条件（exp_006 ablation）

`exp_006_2joint_ppo_shaping` をベースに、**`FORWARD_REQUIRE_FOOT_CONTACT=True` のみ**変更した実験。

## exp_006 との差分

| 項目 | exp_006 | exp_007a |
|------|---------|----------|
| 観測・モデル・PPO・終了 | 同一 | 同一 |
| `FORWARD_REQUIRE_FOOT_CONTACT` | `False` | **`True`** |

前進報酬（`forward_imu` / `forward_foot`）は、`foot_plate` が床に接地している制御 step のみ付与される（`reward.py` の `_forward_component`）。

## 学習

`mujoco-sim` ディレクトリで:

```bash
python -m mujoco_rl_sim.experiments.exp_007a_2joint_ppo_shaping.train
```

チェックポイント: `mujoco_rl_sim/runs/exp_007a_2joint_ppo_shaping/run_YYYYMMDD_HHMMSS/`

**注意**: `obs_dim=25` の exp_006 チェックポイントはそのまま読み込めるが、報酬が変わるため **再学習が必要**。

## 可視化

```bash
python -m mujoco_rl_sim.experiments.exp_007a_2joint_ppo_shaping.visualize \
  --checkpoint run_YYYYMMDD_HHMMSS/final.pt
```

## ロールアウト分析（任意）

```bash
python -m mujoco_rl_sim.experiments.exp_007a_2joint_ppo_shaping.analyze_rollout \
  --checkpoint run_YYYYMMDD_HHMMSS/latest.pt --stochastic --seed 42
```

## 関連

- [exp_006 README](../exp_006_2joint_ppo_shaping/README.md)
