# exp_030 — ディレクトリ構成とレイヤー

## ディレクトリ構成

| パス | 内容 |
|------|------|
| `train.py`, `visualize.py` | 学習・可視化の入口（`@hydra.main`） |
| `conf/` | Hydra 設定正本（YAML + `schema/app_config.py`） |
| `lib/experiment_context.py` | 実行時設定の束ね（DI ルート） |
| `package_meta.py`, `_paths.py` | パス・メタ |
| `sim/` | 環境・観測・報酬・終了・warmup |
| `rl/` | PPO・チェックポイント・W&B |
| `eval/` | チェックポイント評価（仕様・ノイズ・集計・レポート） |
| `scripts/` | `eval.py`・ロールアウト解析・warmup プレビュー・並列学習 |
| `contract/` | 観測契約 `biped_walk_v1`・PPO ループ |
| `lib/` | ctrl・正規化・Hydra 保存・dispatch マージ |
| `telemetry/`, `mujoco_sim_common/` | Hub・viewer 共有 |

## レイヤー境界

```text
train.py（入口）
  → lib/（設定合成・ctx・seed）
  → contract/session.py（学習ループ）
       → bindings（exp 固有の factory）
       → sim/env.py（MuJoCo タスク）
       → rl/agent.py（PPO）
```

| 層 | 責務 | 探索中に触る頻度 |
|----|------|------------------|
| `conf/` | 係数・preset | 高 |
| `sim/` | タスク（報酬・観測・終了） | 高 |
| `contract/` | 学習ループ・テレメトリ契約 | 中 |
| `rl/` | PPO・ログ | 低〜中 |
| `lib/` | 起動インフラ | 低 |

## チェックポイント

`mujoco_rl_sim/runs/exp_030_biped_ppo_walk/`（実験フォルダ外・CWD 非依存）。
