# アルゴリズム編 — 目次

yuuki-lab で触れる・触った強化学習アルゴリズムの解説です。

## 比較（ざっくり）

| アルゴリズム | 方策/価値 | on/off | 行動空間 | yuuki-lab での位置づけ |
|-------------|----------|--------|---------|----------------------|
| [DQN](dqn.md) | 価値 | off | 離散 | アーカイブ・対比用 |
| [A2C/A3C](a2c-a3c.md) | 両方 | on | 連続/離散 | archive exp_001 等 |
| [PPO](ppo.md) | 両方 | on | 連続 | **本線（Isaac Lab）** |
| [SAC/TD3](sac-td3.md) | 両方 | off | 連続 | 将来の候補（概要） |

## 読む順序（PPO 理解向け）

1. [policy-gradient.md](policy-gradient.md) — 方策を直接最適化する考え方  
2. [actor-critic.md](actor-critic.md) — critic と advantage  
3. [ppo.md](ppo.md) — 本線 algo の詳細  

## 実装との対応

| algo | コード（本線: Isaac Lab） | 参照（MuJoCo exp_030） |
|------|--------------------------|------------------------|
| PPO | RSL-RL + `agents/rsl_rl_ppo_cfg.py` | `rl/agent.py` |
| 学習ループ | `scripts/rsl_rl/train.py` | `contract/session.py` |
| 設定 | `biped_ppo_walk_env_cfg.py` 等 | `conf/ppo/default.yaml` |

本線の実験正本: [isaac_biped_ppo_walk](../../experiments/isaac_biped_ppo_walk/README.md)。  
MuJoCo 由来の数値・ログキーは [experiments/exp_030](../../experiments/exp_030_biped_ppo_walk/README.md) を参照。
