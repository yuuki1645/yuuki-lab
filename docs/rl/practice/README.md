# 実務編 — 目次

シミュレーション・歩行 RL で **日々の判断** に効くトピックです。  
実験固有の数値・仕様は [experiments/](../../experiments/README.md) を正本とし、ここは一般原則を述べます。

## 一覧

| ファイル | 内容 |
|---------|------|
| [reward-design.md](reward-design.md) | shaping・sparse/dense・ハックの見分け方 |
| [termination-and-truncation.md](termination-and-truncation.md) | terminated vs truncated |
| [observation-and-normalization.md](observation-and-normalization.md) | 観測設計の原則 |
| [evaluation.md](evaluation.md) | train 指標 vs eval 指標 |
| [hyperparameters.md](hyperparameters.md) | PPO ハイパラの調整 |
| [parallel-rollout.md](parallel-rollout.md) | VecEnv・スループット |
| [domain-randomization.md](domain-randomization.md) | DR の考え方 |
| [common-pitfalls.md](common-pitfalls.md) | よくある落とし穴 |

## 本線・参照へのリンク

| 一般論（本フォルダ） | 本線（Isaac） | 参照（MuJoCo exp_030） |
|---------------------|---------------|------------------------|
| reward-design | [biped_walk_env_cfg.py](../../../isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/manager_based/biped_walk/biped_walk_env_cfg.py) | [reward.md](../../experiments/exp_030_biped_ppo_walk/reward.md) |
| evaluation | [isaac-lab/README.md](../../../isaac-lab/README.md) | [evaluation.md](../../experiments/exp_030_biped_ppo_walk/evaluation.md) |
| parallel-rollout | `BipedWalkEnvCfg` の `num_envs` | [training-parallel.md](../../experiments/exp_030_biped_ppo_walk/training-parallel.md) |
| termination | `biped_walk_env_cfg.py` の `TerminationsCfg` | [termination.md](../../experiments/exp_030_biped_ppo_walk/termination.md) |
