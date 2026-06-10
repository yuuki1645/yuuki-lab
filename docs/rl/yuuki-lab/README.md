# yuuki-lab との接続

本フォルダは **汎用 RL ドキュメント** と **本リポジトリの実験・コード** をつなぎます。

## 3 層の docs

```text
docs/rl/              … 理論・algo・実務の一般論（学び直し・検品用）
docs/experiments/     … 各 exp の正本（報酬係数・eval 仕様・ワークフロー）
experiments/exp_*/    … コード・Hydra・runs
```

| 質問 | 見る場所 |
|------|---------|
| PPO の clip とは | [algorithms/ppo.md](../algorithms/ppo.md) |
| exp_030 の forward_imu の式 | [experiments/exp_030/reward.md](../../experiments/exp_030_biped_ppo_walk/reward.md) |
| どのファイルを編集するか | [experiments/exp_030/code-reading.md](../../experiments/exp_030_biped_ppo_walk/code-reading.md) |

## ファイル一覧

| ファイル | 内容 |
|---------|------|
| [docs-map.md](docs-map.md) | 全 docs の関係図 |
| [exp030-bridge.md](exp030-bridge.md) | rl/ の各トピック → exp_030 コード |
| [sutton-barto-map.md](sutton-barto-map.md) | SB 章 ↔ rl/foundations |

## 本線実験へのリンク

- [exp_030 README](../../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/README.md)
- [exp_030 詳細 docs](../../experiments/exp_030_biped_ppo_walk/README.md)
- [トップ README](../../../README.md)
