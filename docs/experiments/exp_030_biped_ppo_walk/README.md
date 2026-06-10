# exp_030 詳細ドキュメント

**交互片脚歩行 PPO**（`biped_walk_v1`、観測 51 次元）の詳細解説。  
実験フォルダの入口は [experiments/exp_030_biped_ppo_walk/README.md](../../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/README.md)。  
落とし穴・エージェント向け要点は [AGENTS.md](../../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/AGENTS.md)。

## ドキュメント一覧

| ドキュメント | 内容 |
|-------------|------|
| [quickstart.md](quickstart.md) | 実行・pytest・補助 CLI |
| [workflow.md](workflow.md) | 強化学習実験ワークフロー（スモーク→本番→eval→比較） |
| [hydra.md](hydra.md) | Hydra 設定・CLI override・run 再現 |
| [code-reading.md](code-reading.md) | コードリーディング手引き・変更対応表 |
| [architecture.md](architecture.md) | ディレクトリ構成・レイヤー境界 |
| [training-parallel.md](training-parallel.md) | Subproc VecEnv・スループット・Domain Randomization |
| [reward.md](reward.md) | **報酬設計の正本**（`sim/reward.py`） |
| [termination.md](termination.md) | **終了条件と終了ペナルティの正本** |
| [evaluation.md](evaluation.md) | eval v0 仕様・比較・デバッグ |
| [sweep.md](sweep.md) | sweep（AWS / dispatch） |
| [observation.md](observation.md) | 観測の追加次元（idx 12–14） |

## 実装の正本（コード）

| 領域 | 正本 |
|------|------|
| 報酬 | `sim/reward.py` + `conf/reward/` → [reward.md](reward.md) |
| 終了 | `sim/termination.py` + `conf/termination/` → [termination.md](termination.md) |
| 観測 idx 表 | `contract/biped_walk_v1.py` または `python -m contract markdown` |
| 学習ループ | `train.py` → `contract/session.py` |
| run 設定 | `runs/<run>/.hydra/config.yaml` |

## 報酬・終了を変更したとき

`sim/reward.py` / `sim/termination.py` / `conf/` を変えたら、対応する **docs の正本**（[reward.md](reward.md) / [termination.md](termination.md)）を更新する。未更新は **作業未完了** とみなす（[experiments/AGENTS.md](../../../mujoco-sim/mujoco_rl_sim/experiments/AGENTS.md) 参照）。
