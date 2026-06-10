# 強化学習ドキュメント（yuuki-lab）

MuJoCo 歩行実験で使う **強化学習の汎用解説** です。  
実験固有の詳細（報酬係数・終了条件・ワークフロー）は [experiments/](../experiments/README.md) に、人体・実機の数値は [human_joint_kinematics.md](../human_joint_kinematics.md) 等に置きます。

## この docs の位置づけ

```text
docs/rl/           … 理論・アルゴリズム・実務の一般論（本フォルダ）
docs/experiments/  … 各 exp の正本（exp_030 の reward.md 等）
コード             … mujoco-sim/mujoco_rl_sim/experiments/exp_030/...
```

## 推奨読みルート

### ルート A: いま exp_030 を回している

1. [algorithms/ppo.md](algorithms/ppo.md) — いま使っている algo
2. [practice/reward-design.md](practice/reward-design.md) — 報酬の考え方
3. [practice/evaluation.md](practice/evaluation.md) — train と eval の分離
4. [yuuki-lab/exp030-bridge.md](yuuki-lab/exp030-bridge.md) — 理論とコードの対応
5. [experiments/exp_030_biped_ppo_walk/](../experiments/exp_030_biped_ppo_walk/README.md) — 実験の正本

### ルート B: Sutton & Barto 学び直し

1. [yuuki-lab/sutton-barto-map.md](yuuki-lab/sutton-barto-map.md) — 章とファイルの対応
2. [foundations/](foundations/README.md) — 基礎編（01〜07）
3. [algorithms/policy-gradient.md](algorithms/policy-gradient.md) → [ppo.md](algorithms/ppo.md)
4. [yuuki-lab/exp030-bridge.md](yuuki-lab/exp030-bridge.md)

### ルート C: AI の出力を検品したい

1. [glossary.md](glossary.md) — 用語の共通言語
2. [practice/common-pitfalls.md](practice/common-pitfalls.md) — よくある誤り
3. [practice/hyperparameters.md](practice/hyperparameters.md) — ハイパラの意味

## ドキュメント一覧

| フォルダ | 内容 |
|---------|------|
| [foundations/](foundations/README.md) | MDP・return・TD・探索など基礎 |
| [algorithms/](algorithms/README.md) | PPO・方策勾配・Actor-Critic 等 |
| [practice/](practice/README.md) | 報酬設計・eval・DR・落とし穴 |
| [yuuki-lab/](yuuki-lab/README.md) | 本リポジトリとの接続 |
| [glossary.md](glossary.md) | 用語集 |
| [references.md](references.md) | 書籍・論文リンク |

## 関連ドキュメント（リポジトリ内）

| リンク | 内容 |
|--------|------|
| [experiments/exp_030](../experiments/exp_030_biped_ppo_walk/README.md) | 本線実験の詳細 |
| [control_timing_human_rl.md](../control_timing_human_rl.md) | 人体 Hz と RL step |
| [aws/README.md](../../aws/README.md) | AWS 並列学習 |
| [トップ README](../../README.md) | リポジトリ全体の導線 |
