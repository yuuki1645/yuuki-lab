---
name: rl-improvement-loop
description: >-
  Runs the Isaac Lab RL improvement loop for YuukiLab-BipedWalk-v0
  (tasks/manager_based/biped_walk): analyze W&B project yuuki_biped_walk,
  change one hypothesis in that task, smoke-test, then train. Do not use
  removed tasks (biped_ppo_walk, DirectRLEnv, YuukiLab-BipedPpoWalk-*).
---

# Isaac Lab RL 改善ループ（biped_walk）

現行タスクは **`YuukiLab-BipedWalk-v0`** だけです。コードは `isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/manager_based/biped_walk/` です。

削除済みの `biped_ppo_walk`（Direct / 旧 Manager）は使いません。Gym ID `YuukiLab-BipedPpoWalk-*`、ログ名 `biped_ppo_walk`、`eval_biped_walk.py` の 5 m 成功率も、現行の採点ではありません。

## 入口

| 項目 | 場所 |
|------|------|
| 手順 | `isaac-lab/README.md` |
| 仕様 | `biped_walk_env_cfg.py` |
| 報酬・観測・終了の実装 | 同じディレクトリの `mdp/` |
| PPO | `agents/rsl_rl_ppo_cfg.py` |
| 起動確認 | `isaac-lab/scripts/smoke_biped_walk.py` |
| 学習 | `isaac-lab/scripts/rsl_rl/train.py --task YuukiLab-BipedWalk-v0` |
| 再生 | `play.py --task YuukiLab-BipedWalk-Play-v0` |
| ログ | `isaac-lab/logs/rsl_rl/yuuki_biped_walk/` |
| W&B | プロジェクト `yuuki_biped_walk` |

ロボットは `assets/robots/yuuki_legs` です。形状の数値は `robot_description/yuuki_biped.yaml` で、このスキルから学習タスクを増やしません。

MuJoCo の `exp_030` は過去の実験です。報酬の意図を推測する材料にはしてよく、学習の実行先にはしません。

## ループ

ユーザーが目的を言っているときだけ、その目的に達するまで次を繰り返します。目的が数値で無いときは、目的を確認してから学習します。5 m 歩行のような、消したタスクの目標を復活させません。

```
[1] 前回の yuuki_biped_walk を見る（W&B / logs / TensorBoard）
[2] 仮説を 1 つ決める
[3] biped_walk の 1 か所だけ変える
[4] smoke_biped_walk.py で起動を確認する
[5] 短い学習で方向を見てから、本番または fine-tune
[6] ログの報酬と、必要なら play.py で採点する
[7] ユーザーの目的と照らして、未達なら [1] へ
```

専用の定量 eval スクリプトは、このタスクにはありません。`scripts/eval_biped_walk.py` は旧環境の内部状態を読んでいたので削除済みです。代わりに、学習ログへ出ている報酬と、`YuukiLab-BipedWalk-Play-v0` の再生を使います。

### 原則

| 原則 | 内容 |
|------|------|
| 1 run = 1 仮説 | 報酬、終了、PPO のうち 1 軸だけ変える |
| 仕様は cfg | 観測・行動・報酬・終了の意味は `biped_walk_env_cfg.py` を読む |
| スモーク必須 | 本番の前に `smoke_biped_walk.py` が通ること |
| 記録 | ユーザーがファイルを指定したときだけ残す。`docs/experiments/` に本線の実験フォルダは作らない |

### 学習コマンド

作業ディレクトリは `isaac-lab/` です。

```powershell
python scripts/smoke_biped_walk.py

python scripts/rsl_rl/train.py `
  --task YuukiLab-BipedWalk-v0 `
  --headless --num_envs 64 --max_iterations 5 `
  --run_name smoke_<slug>

python scripts/rsl_rl/train.py `
  --task YuukiLab-BipedWalk-v0 `
  --headless `
  --run_name <slug>
```

継続は `--resume --load_run <run_dir_name> --checkpoint model_XXXX.pt` です。`save_interval` は 50 です。

### 変更してよいファイル

| ファイル | 内容 |
|----------|------|
| `biped_walk_env_cfg.py` | シーン、行動スケール、報酬係数、終了、周期 |
| `mdp/` | 報酬・観測・コマンドの実装 |
| `agents/rsl_rl_ppo_cfg.py` | PPO |

環境が落ちる、NaN になる、指標が仮説と逆に動くときは、その仮説を本番へ進めません。
