# exp_030 ブリッジ — 理論とコードの対応

[rl/](../README.md) の各トピックが、MuJoCo exp_030 の **どこに現れるか** を対応づけます。  
> **現行の学習本線は [Isaac Lab](../../../isaac-lab/README.md)**。本ページは由来実装（参照）との対応表です。  
> Isaac 側の入口: [isaac_biped_ppo_walk](../../experiments/isaac_biped_ppo_walk/README.md)

## MDP の写像

| RL 概念 | exp_030 |
|---------|---------|
| 状態 $s$ | MuJoCo 内部状態（質点・関節・接触） |
| 観測 | 51 次元 `biped_walk_v1`（`sim/observation.py`） |
| 行動 $a$ | 関節トルク（方策 MLP 出力） |
| 報酬 $r$ | `sim/reward.py` + `env.py` の終了・接触項 |
| $\gamma$ | `ppo.gamma_per_physics_step` = 0.99 |
| エピソード終了 | `sim/termination.py` + 30 s truncation |

→ [foundations/01-mdp.md](../foundations/01-mdp.md)

## PPO の写像

| PPO 要素 | 場所 |
|---------|------|
| Actor / Critic MLP | `rl/agent.py` |
| rollout 収集 | `contract/session.py`（`_collect_rollout_subproc`） |
| GAE / clip / entropy | `rl/agent.py` |
| ハイパラ | `conf/ppo/default.yaml` |
| VecEnv | `sim/subproc_vec_env.py`, `runtime.num_envs` |

→ [algorithms/ppo.md](../algorithms/ppo.md)

## 報酬設計の写像

| 一般論 | exp_030 詳細 |
|--------|-------------|
| [practice/reward-design.md](../practice/reward-design.md) | [experiments/exp_030/reward.md](../../experiments/exp_030_biped_ppo_walk/reward.md) |
| shaping / ENABLE | `conf/reward/baseline.yaml`, `walk_shaping_on.yaml` |
| 片足支持ゲート | `sim/episode_state.py`, `reward.forward_require_single_support` |
| 歩行位相の背景 | [human_joint_kinematics.md](../../human_joint_kinematics.md) |

## 評価の写像

| 一般論 | exp_030 |
|--------|---------|
| [practice/evaluation.md](../practice/evaluation.md) | [experiments/exp_030/evaluation.md](../../experiments/exp_030_biped_ppo_walk/evaluation.md) |
| 主指標 | `displacement_x_mean`（50 試行） |
| 比較 CLI | `scripts/eval_compare.py` |

## ワークフローの写像

| 段階 | ドキュメント | コマンド例 |
|------|-------------|-----------|
| スモーク | [workflow.md](../../experiments/exp_030_biped_ppo_walk/workflow.md) | `python train.py training=smoke runtime=fast` |
| 本番 | 同上 | `python train.py runtime=fast` |
| 比較 | 同上 | `python scripts/eval_compare.py` |

## 読む順（復習用）

1. [foundations/01-mdp.md](../foundations/01-mdp.md)  
2. [algorithms/ppo.md](../algorithms/ppo.md)  
3. 本ページでコードを確認  
4. [experiments/exp_030/code-reading.md](../../experiments/exp_030_biped_ppo_walk/code-reading.md)  
5. [experiments/exp_030/reward.md](../../experiments/exp_030_biped_ppo_walk/reward.md)

## 次に読む

- [sutton-barto-map.md](sutton-barto-map.md)
- [docs-map.md](docs-map.md)
