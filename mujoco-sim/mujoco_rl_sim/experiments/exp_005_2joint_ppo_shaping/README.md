# exp_005: 2 関節脚 PPO + reward shaping（exp_004 比較用）

`exp_004_2joint_a2c_shaping` と **観測・報酬・終了・MuJoCo モデル・制御レートは同一**。
強化学習アルゴリズムのみ **A2C → PPO（GAE + clipped surrogate）** に変更した ablation 実験。

## exp_004 との差分（アルゴリズムのみ）

| 項目 | exp_004 (A2C) | exp_005 (PPO) |
|------|---------------|---------------|
| 方策更新 | 1-step TD advantage、ミニバッチ複数 `step`（clip なし） | **GAE(λ)** + **PPO clip**（`CLIP_EPS=0.2`） |
| ロールアウト再利用 | 1 パス相当 | **`PPO_EPOCHS=8`** |
| 収集時 `log_prob` | なし | **保存して方策比** \(r=\exp(\log\pi_{\mathrm{new}}-\log\pi_{\mathrm{old}})\) |
| KL 早期打ち切り | — | `TARGET_KL=0.02`（epoch 平均 KL が閾値超で打ち切り） |
| wandb train/* | policy / value / entropy | 上記 + **`approx_kl`**, **`clip_fraction`** |

観測・shaping・終了・`GAMMA`・`LR`・`ROLLOUT_STEPS`・ネットワーク構造（64-64）は exp_004 に合わせた出発点。

## 学習

`mujoco-sim` ディレクトリで:

```bash
python -m mujoco_rl_sim.experiments.exp_005_2joint_ppo_shaping.train
```

チェックポイント: `mujoco_rl_sim/runs/exp_005_2joint_ppo_shaping/run_YYYYMMDD_HHMMSS/`

再開例:

```bash
python -m mujoco_rl_sim.experiments.exp_005_2joint_ppo_shaping.train \
  --resume run_YYYYMMDD_HHMMSS/update_005000.pt \
  --lr 1e-4 \
  --num-updates 1500
```

## 可視化

```bash
python -m mujoco_rl_sim.experiments.exp_005_2joint_ppo_shaping.visualize \
  --checkpoint run_YYYYMMDD_HHMMSS/final.pt
```

## wandb での A2C 比較

- 横軸は **env step**（`episode/*` の step）で exp_004 と重ねる
- `episode/return`, `forward_reward_sum`, `shaping_sum`, `length` は定義が同一
- exp_005 のみ: `train/approx_kl`, `train/clip_fraction`

## 関連

- [exp_004 README](../exp_004_2joint_a2c_shaping/README.md)（報酬・shaping のベースライン）
- [exp_003 README](../exp_003_2joint_a2c/README.md)
