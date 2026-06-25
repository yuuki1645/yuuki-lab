---
name: rl-improvement-loop
description: >-
  Runs the yuuki-lab RL improvement loop: analyze prior training results, propose
  and implement one-hypothesis code changes, execute smoke/full training, evaluate,
  and record each iteration in markdown until a stated goal is met. Use when improving
  biped_ppo_walk, Isaac Lab or MuJoCo exp_030 training, analyzing W&B/TensorBoard logs,
  tuning rewards/termination/PPO, or when the user asks to iterate RL until a target
  (e.g. stable 5 m walk) is achieved.
---

# RL Improvement Loop

yuuki-lab の強化学習を **目的達成まで自動で反復** する。1 反復ごとに分析・判断・実装・実行・記録を行い、**目的未達成のうちにループを終了しない**。

## 目的の定義（開始前に必ず確定）

ユーザーが目的を明示しない場合は確認する。例:

| 目的 | 達成条件（Isaac Lab） | 達成条件（MuJoCo exp_030） |
|------|----------------------|---------------------------|
| 5 m 安定歩行 | `eval_biped_walk.py` で **Success rate >= 5 m ≥ 80%**（`--episodes` 十分）かつ平均 `episode_displacement_x` ≥ 4 m | `eval/displacement_x_mean` が過去ベスト以上かつ CI95 が前進を支持 |
| 15 m 歩行 | Success rate >= 15 m ≥ 50% | 同上（15 m 基準） |
| カスタム | ユーザー指定の数値・挙動 | ユーザー指定 |

**ループ終了は達成条件を満たしたときのみ。** 学習が収束した・時間がかかった・改善が見込めない、だけでは終了しない。ブロック時は `iterations.md` に理由を書き、ユーザーに判断を求める。

## 記録の正本

| ファイル | 用途 |
|----------|------|
| `docs/experiments/isaac_biped_ppo_walk/iterations.md` | Isaac Lab 反復ログ（**各イテレーションを追記**） |
| `docs/experiments/exp_030_biped_ppo_walk/` | MuJoCo 本線の workflow・eval 正本 |
| 実験フォルダ `MEMO.md` | 短いメモ（詳細は iterations.md） |

新イテレーションは **ファイル末尾に追記**（古い記録は消さない）。テンプレートは [iteration-log-template.md](iteration-log-template.md)。

## ループ全体（必ずこの順序）

```
[0] 目的・達成条件を確認
[1] 前回 run を分析
[2] 仮説を 1 つ決める（1 run = 1 仮説）
[3] iterations.md に「分析・判断」を先に書く（実装前）
[4] コード変更（報酬/終了/PPO の 1 軸）
[5] スモーク学習 → 定量確認
[6] Go なら本番/fine-tune 学習（バックグラウンド可）
[7] 学習完了を待つ（/loop または動的 wake）
[8] eval + W&B/TB で採点
[9] iterations.md に「実装・結果・次アクション」を追記
[10] 達成条件チェック → 未達なら [1] へ（終了しない）
```

### 原則（exp_030 workflow 継承）

| 原則 | 内容 |
|------|------|
| **1 run = 1 仮説** | 報酬係数・ENABLE・終了条件など **1 軸だけ** 変更 |
| **採点は eval** | 学習曲線だけで成功と判断しない |
| **スモーク必須** | 本番前に短い学習でクラッシュ・NaN・方向性を確認 |
| **再現性** | `run_name`（例 `v25_...`）、`biped_ppo_walk_env_cfg.py` の vNN コメント、git diff を記録 |
| **記録先行** | 実装前に「何を変えるか・なぜ」を MD に書いてからコードを触る |

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

MuJoCo の場合は `eval_report.json` と `eval_compare.py` を正本とする（`docs/experiments/exp_030_biped_ppo_walk/workflow.md`）。

### 2. 改善判断

分析から **1 つの仮説** を選ぶ。判断は次の形式で `iterations.md` に書く:

- **観察**: 数値・ログから何が起きているか
- **仮説**: なぜそうなっているか（因果）
- **提案変更**: どのファイルのどのパラメータをどう変えるか
- **期待効果**: どの指標がどう動くか
- **リスク**: 悪化しうる副作用

変更対象の正本:

- Isaac 報酬/終了: `isaac-lab/source/yuuki_isaac_lab/.../biped_ppo_walk/biped_ppo_walk_env_cfg.py`
- Isaac MDP: `mdp/reward.py`, `mdp/termination.py`, `mdp/episode_state.py`
- PPO: `agents/rsl_rl_ppo_cfg.py`
- MuJoCo: `conf/reward/`, `conf/training/`（Hydra）

### 3. 実装

- バージョンコメントを更新（例: `v25 (...): <仮説の一行要約>`）
- **1 軸のみ** 変更。複数変更が必要ならイテレーションを分割
- 実装後、`iterations.md` の「実際の変更」節を更新（diff の要約 + 根拠）

### 4. 学習実行

作業ディレクトリ: `isaac-lab/`

```powershell
# スモーク（必須）
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 64 --max_iterations 5 --run_name vNN_smoke_<slug>

# 本番 / fine-tune
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 4096 --run_name vNN_<slug> --max_iterations 600
# 前 run から継続する場合
# --resume --load_run <prev_run_dir> --checkpoint model_XXXX.pt
```

MuJoCo:

```bash
cd mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk
python train.py training=smoke runtime=fast
python train.py runtime=fast
```

**長時間学習**: バックグラウンド実行 + [loop skill](file:///C:/Users/yuukilab/.cursor/skills-cursor/loop/SKILL.md) で完了を監視。学習中に別仮説を混ぜない。

### 5. 評価

```powershell
cd isaac-lab
python scripts/eval_biped_walk.py --load_run <run_dir_name> --episodes 10 --num_envs 64
```

Go/No-Go（スモーク後）:

| 判断 | 基準 |
|------|------|
| **No-Go** | クラッシュ、NaN、主指標が明確に悪化、想定外のハック挙動 |
| **Go** | クラッシュなし、主指標が横ばい〜改善、仮説の方向性がログで確認できる |

### 6. イテレーション記録の完了

[iteration-log-template.md](iteration-log-template.md) に従い、**結果サマリー** を必ず含める:

- run 名・チェックポイント・学習イテレーション数
- eval の Success rate / mean displacement
- W&B 主要メトリクスの前回比
- 達成条件に対する距離（例: 「5 m 成功率 12% → 34%、目標 80% 未達」）
- **次イテレーションの仮説**（未達の場合）

## ループ継続ルール（重要）

1. **目的達成まで反復する。** 1 回の学習で改善しなくても終了しない
2. **各ターンでやること**: 分析 → 記録（判断）→ 実装 → 実行 or 実行監視 → 評価 → 記録（結果）→ 達成判定
3. **学習が走っている間**: 新しい仮説実装を始めない。完了を待ってから eval
4. **3 連続 No-Go** のとき: 仮説の立て方を見直し、`iterations.md` に振り返りを書く（それでもループは継続）
5. **ユーザーが明示的に停止** したときのみループを中断
6. **ハードウェア/環境エラー**（GPU OOM、Isaac 起動失敗）: 記録してリトライ or ユーザーに報告。達成済みとみなさない

### 達成判定チェックリスト

```
- [ ] eval の Success rate が目標値以上
- [ ] 平均 displacement が目標に見合う
- [ ] 明らかなハック挙動がない（片脚率・交互着地率を確認）
- [ ] iterations.md に最終イテレーションの結果が記録済み
```

すべて満たしたらループ終了を宣言し、達成サマリーを `iterations.md` 末尾に書く。

## タスク別クイックリファレンス

| 項目 | Isaac Lab | MuJoCo exp_030 |
|------|-----------|----------------|
| 学習入口 | `isaac-lab/scripts/rsl_rl/train.py` | `experiments/exp_030_biped_ppo_walk/train.py` |
| ログ | `logs/rsl_rl/biped_ppo_walk/` | `runs/exp_030_biped_ppo_walk/` |
| eval | `scripts/eval_biped_walk.py` | `scripts/eval.py` + `eval_compare.py` |
| タスク README | `.../biped_ppo_walk/README.md` | `docs/experiments/exp_030_biped_ppo_walk/` |
| 反復ログ | `docs/experiments/isaac_biped_ppo_walk/iterations.md` | workflow.md + eval_compare |

## 追加リソース

- イテレーション記録テンプレート: [iteration-log-template.md](iteration-log-template.md)
- MuJoCo 標準 workflow: `docs/experiments/exp_030_biped_ppo_walk/workflow.md`
- Isaac タスク詳細: `isaac-lab/source/yuuki_isaac_lab/.../biped_ppo_walk/README.md`
