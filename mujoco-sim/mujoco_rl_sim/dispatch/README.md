# mujoco_rl_sim.dispatch

LAN 内複数 PC 向けの実験ジョブ配布（Coordinator / Worker）。

## 用語

- **Coordinator**: ジョブ台帳（SQLite）と Web UI / API
- **Worker**: ジョブを Pull して各 `experiments/exp_*/train.py` を実行

## セットアップ

```bash
cd mujoco-sim
pip install -e ".[rl,dispatch]"
```

## Coordinator（1台）

```bash
# 例: mujoco-sim/mujoco_rl_sim/dispatch/examples/coordinator.config.example.toml をコピーして編集
python -m mujoco_rl_sim.dispatch.coordinator --config coordinator.config.toml
```

- Web UI: http://127.0.0.1:8790/
- DB 既定: `mujoco_rl_sim/dispatch_data/coordinator.db`

## sweep 登録

```bash
python -m mujoco_rl_sim.dispatch.coordinator.cli plan --file \
  mujoco_rl_sim/experiments/exp_026_biped_ppo_hop_balance/sweeps/baseline_10seed.yaml

python -m mujoco_rl_sim.dispatch.coordinator.cli --config coordinator.config.toml sweep register --file \
  mujoco_rl_sim/experiments/exp_026_biped_ppo_hop_balance/sweeps/baseline_10seed.yaml
```

## Worker（各PC）

```bash
# worker.config.toml を端末ごとに用意（git 管理外推奨）
python -m mujoco_rl_sim.dispatch.worker --config worker.config.toml
```

Coordinator PC でも Worker を起動すれば、同じ Pull API で学習に参加できます。

## W&B

- `project`: 各 exp の `config.WANDB_PROJECT`（exp フォルダ名）
- `group`: `config_hash`
- `tags`: `sweep:<sweep_id>` など（`DISPATCH_WANDB_EXTRA_TAGS`）

## 環境変数（Worker → train）

| 変数 | 用途 |
|------|------|
| `DISPATCH_RUN_ID` | run 名 / 追跡 |
| `DISPATCH_SWEEP_ID` | W&B tag |
| `DISPATCH_CONFIG_HASH` | W&B group |
| `DISPATCH_WANDB_GROUP` | W&B group |
| `DISPATCH_WANDB_EXTRA_TAGS` | 追加 tag（カンマ区切り） |

学習終了時に `dispatch_summary.json` を exp フォルダへ書き、主指標を Coordinator へ報告します（exp_026 の `wandb_logging` 参照）。
