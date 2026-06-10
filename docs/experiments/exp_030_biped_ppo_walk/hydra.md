# exp_030 — Hydra 設定

設定の正本は **`conf/`**。実行時は `ExperimentContext`（`lib/experiment_context.py`）に束ねられ、sim / rl / contract は **DI** で参照する。旧 `config.py`・`--set`・`config_effective.json` は廃止。

### config groups

| group | 役割 | 代表 preset |
|-------|------|-------------|
| `sim` | 物理・観測次元・方策 MLP | `default` |
| `reward` | 報酬 ENABLE・係数 | `baseline`（ミニマル）、`forward55`、`walk_shaping_on` |
| `ppo` | 学習率・clip・GAE | `default` |
| `termination` | 転倒閾値 | `default` |
| `training` | updates・seed・DR・post eval | `prod`（5000）、`smoke`（300） |
| `runtime` | viewer・telemetry・VecEnv | `fast`（本番推奨）、`debug_viewer` |
| `wandb` | W&B on/off | `enabled` / `disabled` |
| `resume` | ckpt 再開 | `none` / `from_ckpt` |

ルート: `conf/config.yaml`（`hydra.job.chdir: false` — cwd は実験ルートのまま）。

### 起動例

```bash
# 既定（training=prod, runtime=fast, wandb=enabled, reward=baseline）
python train.py

# スモーク + 報酬仮説
python train.py training=smoke runtime=fast wandb=disabled reward=forward55

# 単一キー override（Hydra 構文）
python train.py reward.forward_reward_scale=55.0 training.num_updates=1 wandb=disabled

# 過去 run の完全再現（W&B init 前に config を読む）
python train.py --config-path ../../runs/exp_030_biped_ppo_walk/<run>/.hydra --config-name config
```

`justfile` に同等レシピあり（`just smoke`、`just train-fast` 等）。

### AWS 並列（`aws_launch.py`）

自宅 PC から EC2 Spot を起動するランチャー。`--dry-run` → `enabled=true` + `--confirm` の順で使う。  
手順・課金注意・トラブルシュート: [aws/README.md](../../../mujoco-sim/aws/README.md)。

### dispatch 連携（レガシー・LAN）

旧 LAN 向け `mujoco_rl_sim.dispatch` 用。AWS 並列の本線は上記 `aws_launch.py`。  
dispatch job 起動時は次の 2 経路で Hydra cfg に反映される（**後勝ち**）:

1. **legacy argv ブリッジ** — 旧 `--set` / `--num-envs` 等を Hydra override に変換（`lib/dispatch_argv_bridge.py`）
2. **`DISPATCH_CONFIG_OVERRIDES_JSON`** — sweep キーをネストパスへマージ（`lib/dispatch_cfg_merge.py`）

eval / visualize / analyze は ckpt 親 run の `.hydra/config.yaml` から `ExperimentContext` を復元する（eval 本体の試行条件は `eval/` 固定 preset）。
