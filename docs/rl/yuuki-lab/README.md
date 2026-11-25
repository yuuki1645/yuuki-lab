# yuuki-lab との接続

本フォルダは **汎用 RL ドキュメント** と **本リポジトリの実験・コード** をつなぎます。

## 3 層の docs

```text
docs/rl/              … 理論・algo・実務の一般論（学び直し・検品用）
docs/experiments/     … MuJoCo 実験の参照（exp_030）
isaac-lab/            … 本線コード（YuukiLab-BipedWalk-v0）
mujoco-sim/.../exp_*/ … 参照・レガシー（Hydra・報酬設計の由来）
```

| 質問 | 見る場所 |
|------|---------|
| PPO の clip とは | [algorithms/ppo.md](../algorithms/ppo.md) |
| **いま触る実験** | [isaac-lab/README.md](../../../isaac-lab/README.md) |
| Isaac の報酬・観測 | [biped_walk_env_cfg.py](../../../isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/manager_based/biped_walk/biped_walk_env_cfg.py) |
| exp_030 の forward_imu の式（背景） | [experiments/exp_030/reward.md](../../experiments/exp_030_biped_ppo_walk/reward.md) |
| MuJoCo 由来の対応表 | [exp030-bridge.md](exp030-bridge.md) |

## ファイル一覧

| ファイル | 内容 |
|---------|------|
| [docs-map.md](docs-map.md) | 全 docs の関係図 |
| [exp030-bridge.md](exp030-bridge.md) | rl/ の各トピック → exp_030 コード（参照） |
| [sutton-barto-map.md](sutton-barto-map.md) | SB 章 ↔ rl/foundations |

## 本線実験へのリンク

- [isaac-lab/README.md（本線）](../../../isaac-lab/README.md)
- [biped_walk_env_cfg.py](../../../isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/manager_based/biped_walk/biped_walk_env_cfg.py)
- [トップ README](../../../README.md)

### 参照（旧 MuJoCo 本線）

- [exp_030 README](../../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/README.md)
- [exp_030 詳細 docs](../../experiments/exp_030_biped_ppo_walk/README.md)
