---
name: rl-improvement-loop
description: >-
  Runs the Isaac Lab RL improvement loop for biped_ppo_walk: analyze prior training
  results (W&B, TensorBoard, logs), propose and implement one-hypothesis code changes,
  execute smoke/full training, evaluate with eval_biped_walk.py, and record each
  iteration in markdown until a stated goal is met. Use when improving Isaac Lab
  biped walking, analyzing W&B/TensorBoard logs, tuning rewards/termination/PPO in
  yuuki_isaac_lab, or when the user asks to iterate RL until a target (e.g. stable
  5 m walk) is achieved.
---

# Isaac Lab RL Improvement Loop

`isaac-lab/` 上の **biped_ppo_walk** 学習を **目的達成まで自動で反復** する。1 反復ごとに分析・判断・実装・実行・記録を行い、**目的未達成のうちにループを終了しない**。

> **スコープ**: 本スキルは **Isaac Lab 専用**。MuJoCo（exp_030）での学習は対象外。報酬設計の背景参照のみ `docs/experiments/exp_030_biped_ppo_walk/` を読む。

## 目的の定義（開始前に必ず確定）

ユーザーが目的を明示しない場合は確認する。既定例:

| 目的 | 達成条件 |
|------|----------|
| 5 m 安定歩行 | `eval_biped_walk.py` で **Success rate >= 5 m ≥ 80%**（`--episodes 10` 以上）かつ平均 displacement ≥ 4 m |
| 15 m 歩行 | Success rate >= 15 m ≥ 50% |
| カスタム | ユーザー指定の数値・挙動 |

**ループ終了は達成条件を満たしたときのみ。** 学習が収束した・時間がかかった・改善が見込めない、だけでは終了しない。ブロック時は `iterations.md` に理由を書き、ユーザーに判断を求める。

## 記録の正本

| ファイル | 用途 |
|----------|------|
| `docs/experiments/isaac_biped_ppo_walk/iterations.md` | 反復ログ（**各イテレーションを末尾に追記**） |
| `docs/experiments/isaac_biped_ppo_walk/README.md` | 実験入口・目的・クイックコマンド |
| `isaac-lab/source/yuuki_isaac_lab/.../biped_ppo_walk/README.md` | タスク詳細（観測・報酬・実行手順） |

テンプレート: [iteration-log-template.md](iteration-log-template.md)

## ループ全体（必ずこの順序）

```
[0] 目的・達成条件を確認
[1] 前回 Isaac run を分析（W&B / TB / logs）
[2] 仮説を 1 つ決める（1 run = 1 仮説）
[3] iterations.md に「分析・判断」を先に書く（実装前）
[4] yuuki_isaac_lab のコード変更（報酬/終了/PPO の 1 軸）
[5] スモーク学習 → 定量確認
[6] Go なら本番/fine-tune 学習（バックグラウンド可）
[7] 学習完了を待つ（/loop または動的 wake）
[8] eval_biped_walk.py + W&B/TB で採点
[9] iterations.md に「実装・結果・次アクション」を追記
[10] 達成条件チェック → 未達なら [1] へ（終了しない）
```

### 原則

| 原則 | 内容 |
|------|------|
| **1 run = 1 仮説** | 報酬係数・ENABLE・終了条件など **1 軸だけ** 変更 |
| **採点は eval** | 学習曲線だけで成功と判断しない |
| **スモーク必須** | 本番前に短い学習でクラッシュ・NaN・方向性を確認 |
| **再現性** | `--run_name`（例 `v25_...`）、`biped_ppo_walk_env_cfg.py` の vNN コメント、run 内 `params/`・`git/` を記録 |
| **記録先行** | 実装前に「何を変えるか・なぜ」を MD に書いてからコードを触る |
| **Isaac のみ実行** | 学習・eval は `isaac-lab/` で行う。MuJoCo train/eval は呼ばない |

## フェーズ別手順

### 1. 前回結果の分析

**データソース（優先順）:**

1. W&B MCP（`user-wandb`）— プロジェクト `biped_ppo_walk`
2. 最新 run: `isaac-lab/logs/rsl_rl/biped_ppo_walk/<run_dir>/`
3. `params/env.yaml`, `params/agent.yaml`, `git/` スナップショット
4. TensorBoard: `tensorboard --logdir isaac-lab/logs/rsl_rl/biped_ppo_walk`

**見る指標:**

| 指標 | 意味 | 悪化の典型原因 |
|------|------|----------------|
| `Metrics/episode_displacement_x` | +X 移動距離 | 前進報酬不足、転倒多、片脚不足 |
| `Metrics/single_support_ratio` | 片足支持率 | すり足、両足支持ハック |
| `Metrics/alternating_landing_ratio` | 交互着地率 | 同足連続、ピボット停滞 |
| `Metrics/mean_milestone_level` | 距離マイルストーン | 5 m 手前で転倒 |
| `Train/mean_episode_length` | エピソード長 | 早期 terminated |
| `Reward/mean_forward` vs shaping | 報酬内訳 | ハック報酬への偏り |

必要なら `scripts/rsl_rl/play.py` で可視確認。

### 2. 改善判断

分析から **1 つの仮説** を選ぶ。`iterations.md` に書く項目:

- **観察**: 数値・ログから何が起きているか
- **仮説**: なぜそうなっているか（因果）
- **提案変更**: どのファイルのどのパラメータをどう変えるか
- **期待効果**: どの指標がどう動くか
- **リスク**: 悪化しうる副作用

**変更対象の正本**（すべて `isaac-lab/source/yuuki_isaac_lab/.../biped_ppo_walk/` 以下）:

| ファイル | 内容 |
|----------|------|
| `biped_ppo_walk_env_cfg.py` | 報酬係数・終了条件・シーン設定 |
| `mdp/reward.py` | ステップ報酬ロジック |
| `mdp/termination.py` | 姿勢終了判定 |
| `mdp/episode_state.py` | 歩行位相（交互着地・片脚 streak） |
| `agents/rsl_rl_ppo_cfg.py` | PPO ハイパラ |

報酬設計の意図が不明なときのみ `docs/experiments/exp_030_biped_ppo_walk/reward.md` を参照（**MuJoCo で学習はしない**）。

### 3. 実装

- `BipedRewardCfg` 等のバージョンコメントを更新（例: `v25 (...): <仮説の一行要約>`）
- **1 軸のみ** 変更。複数変更が必要ならイテレーションを分割
- パッケージ再インストールが必要な場合: `cd isaac-lab && python -m pip install -e source/yuuki_isaac_lab`
- 実装後、`iterations.md` の「実際の変更」節を更新（diff 要約 + 根拠）

### 4. 学習実行

**作業ディレクトリは常に `isaac-lab/`。**

```powershell
cd isaac-lab

# スモーク（必須）
python scripts/rsl_rl/train.py `
  --task YuukiLab-BipedPpoWalk-Direct-v0 `
  --headless --num_envs 64 --max_iterations 5 `
  --run_name vNN_smoke_<slug>

# 本番 / fine-tune（既定 num_envs=4096, max_iterations=3000）
python scripts/rsl_rl/train.py `
  --task YuukiLab-BipedPpoWalk-Direct-v0 `
  --headless --num_envs 4096 `
  --run_name vNN_<slug> `
  --max_iterations 600

# 前 run から継続
# --resume --load_run <prev_run_dir> --checkpoint model_XXXX.pt
```

| 項目 | 値 |
|------|-----|
| ログ出力 | `isaac-lab/logs/rsl_rl/biped_ppo_walk/<timestamp>_<run_name>/` |
| W&B プロジェクト | `biped_ppo_walk`（既定 online） |
| ckpt 間隔 | `save_interval=400` → `model_400.pt`, `model_800.pt`, ... |

**長時間学習**: バックグラウンド実行 + [loop skill](file:///C:/Users/yuukilab/.cursor/skills-cursor/loop/SKILL.md) で完了を監視。学習中に別仮説を混ぜない。

### 5. 評価

```powershell
cd isaac-lab
python scripts/eval_biped_walk.py --load_run <run_dir_name> --episodes 10 --num_envs 64
```

出力の主指標:
- `Mean episode displacement +X`
- `Success rate >= 5 m` / `>= 15 m`
- `Mean single_support ratio`

Go/No-Go（スモーク後）:

| 判断 | 基準 |
|------|------|
| **No-Go** | クラッシュ、NaN、主指標が明確に悪化、想定外のハック挙動 |
| **Go** | クラッシュなし、主指標が横ばい〜改善、仮説の方向性がログで確認できる |

### 6. イテレーション記録の完了

[iteration-log-template.md](iteration-log-template.md) に従い **結果サマリー** を必ず含める:

- run 名・チェックポイント・学習イテレーション数
- eval の Success rate / mean displacement
- W&B 主要メトリクスの前回比
- 達成条件に対する距離（例: 「5 m 成功率 12% → 34%、目標 80% 未達」）
- **次イテレーションの仮説**（未達の場合）

## ループ継続ルール（重要）

1. **目的達成まで反復する。** 1 回の学習で改善しなくても終了しない
2. **各ターン**: 分析 → 記録（判断）→ 実装 → 実行 or 監視 → eval → 記録（結果）→ 達成判定
3. **学習中**: 新しい仮説実装を始めない。完了を待ってから eval
4. **3 連続 No-Go**: 仮説の立て方を見直し、`iterations.md` に振り返りを書く（ループは継続）
5. **ユーザーが明示的に停止** したときのみ中断
6. **環境エラー**（GPU OOM、Isaac 起動失敗）: 記録してリトライ or ユーザーに報告。達成済みとみなさない

### 達成判定チェックリスト

```
- [ ] eval_biped_walk.py の Success rate が目標値以上
- [ ] 平均 displacement が目標に見合う
- [ ] ハック挙動がない（片脚率・交互着地率を確認）
- [ ] iterations.md に最終イテレーションの結果が記録済み
```

すべて満たしたらループ終了を宣言し、達成サマリーを `iterations.md` 末尾に書く。

## クイックリファレンス

| 項目 | パス |
|------|------|
| 学習 | `isaac-lab/scripts/rsl_rl/train.py` |
| 評価 | `isaac-lab/scripts/eval_biped_walk.py` |
| 可視化 | `isaac-lab/scripts/rsl_rl/play.py` |
| 環境スモーク | `isaac-lab/scripts/smoke_biped_walk.py` |
| ログ | `isaac-lab/logs/rsl_rl/biped_ppo_walk/` |
| タスクコード | `isaac-lab/source/yuuki_isaac_lab/.../biped_ppo_walk/` |
| 反復ログ | `docs/experiments/isaac_biped_ppo_walk/iterations.md` |
| Hub UI（任意） | `robotics-hub` の `/isaac-rl-log` |

## 追加リソース

- イテレーション記録テンプレート: [iteration-log-template.md](iteration-log-template.md)
- タスク詳細: `isaac-lab/source/yuuki_isaac_lab/.../biped_ppo_walk/README.md`
- 報酬設計の背景（参照のみ）: `docs/experiments/exp_030_biped_ppo_walk/reward.md`
