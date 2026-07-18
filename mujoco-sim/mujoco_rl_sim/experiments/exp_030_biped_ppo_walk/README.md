# exp_030: 交互片脚歩行 PPO（exp_029 コピー）

> **リポジトリ強化学習の本線は [Isaac Lab](../../../../isaac-lab/README.md) に移りました。**  
> 本フォルダは MuJoCo 時代の最終系統（参照・レガシー）。新規学習は `isaac-lab/` を使ってください。  
> 実験 docs: [docs/experiments/isaac_biped_ppo_walk](../../../../docs/experiments/isaac_biped_ppo_walk/README.md)

**exp_029** をコピーした作業用 fork です（2026-06）。**コピー時点でコードは exp_029 と同一**で、`runs/` のみ空から開始します。  
exp_029 の run 混在を整理し、**MuJoCo 系統では**以降の作業を本フォルダで行う想定でした。

| 項目 | exp_029 | exp_030 |
|------|---------|---------|
| コード | Hydra + Subproc VecEnv（コピー元） | **コピー時同一**（以降は本フォルダで変更） |
| runs | 既存 run 混在 | **`runs/exp_030_biped_ppo_walk/` を新規使用** |
| ロールアウト | 単一 env 逐次 | **Subproc VecEnv**（`runtime.num_envs`、推奨 8） |
| 設定 | `config.py` + `--set` | **Hydra**（`conf/` + CLI override） |
| テスト / CI | なし | **pytest + GitHub Actions** |

タスク設計の源流は **exp_026** の MLP を維持した **交互片脚歩行** です。

| 項目 | exp_026 | exp_030 |
|------|---------|---------|
| 前進報酬 | 飛翔中も IMU `dx`、両足 `foot_dx` 合算可 | **片足支持時のみ** |
| すり足 | 抑制なし | **`double_support_penalty`** |
| 位相 | push/landing 無効 | **push / landing / 交互着地 / 遊脚離地** |
| 観測 | 48 次元 `biped_ppo_v1` | **51 次元 `biped_walk_v1`** |

## 最短手順

```bash
cd exp_030_biped_ppo_walk
pip install -r requirements.txt
python -m contract validate
python train.py                                    # 本番（training=prod, runtime=fast）
python train.py training=smoke runtime=fast        # スモーク
python scripts/eval_compare.py                     # run 横断比較
```

チェックポイント: `mujoco_rl_sim/runs/exp_030_biped_ppo_walk/`  
採点の主指標: **eval `displacement_x_mean`**（大きいほど前進）。詳細は下記ドキュメント。

## 詳細ドキュメント

**報酬・終了条件・ワークフロー・実装詳細の正本**は `docs/` にあります（本 README は入口のみ）。

→ **[../../../../docs/experiments/exp_030_biped_ppo_walk/README.md](../../../../docs/experiments/exp_030_biped_ppo_walk/README.md)**（目次）

| ドキュメント | 内容 |
|-------------|------|
| [quickstart.md](../../../../docs/experiments/exp_030_biped_ppo_walk/quickstart.md) | 実行・pytest・補助 CLI |
| [workflow.md](../../../../docs/experiments/exp_030_biped_ppo_walk/workflow.md) | スモーク→本番→eval の標準手順 |
| [hydra.md](../../../../docs/experiments/exp_030_biped_ppo_walk/hydra.md) | Hydra 設定・override |
| [code-reading.md](../../../../docs/experiments/exp_030_biped_ppo_walk/code-reading.md) | コードリーディング手引き |
| [architecture.md](../../../../docs/experiments/exp_030_biped_ppo_walk/architecture.md) | ディレクトリ構成・レイヤー |
| [training-parallel.md](../../../../docs/experiments/exp_030_biped_ppo_walk/training-parallel.md) | VecEnv・スループット・DR |
| [reward.md](../../../../docs/experiments/exp_030_biped_ppo_walk/reward.md) | **報酬設計の正本** |
| [termination.md](../../../../docs/experiments/exp_030_biped_ppo_walk/termination.md) | **終了条件の正本** |
| [evaluation.md](../../../../docs/experiments/exp_030_biped_ppo_walk/evaluation.md) | eval v0 仕様 |
| [sweep.md](../../../../docs/experiments/exp_030_biped_ppo_walk/sweep.md) | sweep（AWS / dispatch） |
| [observation.md](../../../../docs/experiments/exp_030_biped_ppo_walk/observation.md) | 観測の追加次元 |

AI エージェント向け要点: [AGENTS.md](AGENTS.md)
