# isaac-lab

[yuuki-lab](https://github.com/yuuki1645/yuuki-lab) 内の **Isaac Lab 拡張**です。  
**リポジトリの強化学習本線**（両脚・交互片脚歩行 PPO）です。由来は MuJoCo [exp_030](../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) で、報酬設計の背景はそこを参照します。

実験ドキュメント: [docs/experiments/isaac_biped_ppo_walk/](../docs/experiments/isaac_biped_ppo_walk/README.md)  
改善ループ（AI）: [.cursor/skills/rl-improvement-loop/SKILL.md](../.cursor/skills/rl-improvement-loop/SKILL.md)

## 前提

- [Isaac Lab](https://isaac-sim.github.io/IsaacLab/) と Isaac Sim は **このリポジトリ外** にインストール済みであること
- Python 3.10+（`env_isaaclab` 等の conda 環境を推奨）

## セットアップ

```bash
cd isaac-lab
python -m pip install -e source/yuuki_isaac_lab
```

## タスク一覧

```bash
python scripts/list_envs.py --headless
```

登録タスク（接頭辞 `YuukiLab-`）:

| Task ID | 用途 | ワークフロー |
|---------|------|--------------|
| `YuukiLab-BipedPpoWalk-Direct-v0` | 学習 | DirectRLEnv |
| `YuukiLab-BipedPpoWalk-Direct-Play-v0` | 再生・録画 | DirectRLEnv |
| `YuukiLab-BipedPpoWalk-v0` | 学習 | ManagerBasedRLEnv |
| `YuukiLab-BipedPpoWalk-Play-v0` | 再生・録画 | ManagerBasedRLEnv |

**Direct 版タスク解説**: [source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/direct/biped_ppo_walk/README.md](source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/direct/biped_ppo_walk/README.md)

**Manager-Based 版**: [source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/manager_based/biped_ppo_walk/README.md](source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/manager_based/biped_ppo_walk/README.md)

## 学習

**スモークテスト**とは、本番学習の前に「環境と学習ループが起動するか」だけを短時間確認する実行です。  
歩行の出来は見ず、`num_envs` を少なめ・`max_iterations` をごく短くします。`scripts/manager_based/smoke.py` は学習なしで環境を数ステップ回す、さらに軽い起動確認です。

**1行で書く（PowerShell / bash 共通・おすすめ）**

```powershell
# スモーク（Direct）— 起動確認のみ
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 64 --max_iterations 5

# スモーク（Manager-Based）
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --headless --num_envs 64 --max_iterations 5

# 本番（例: Direct）
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 4096

# 本番（例: Manager-Based）
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --headless --num_envs 4096
```

**PowerShell で複数行に分ける場合**は行末に **バッククォート `` ` ``**（`\` ではない）:

```powershell
python scripts/rsl_rl/train.py `
  --task YuukiLab-BipedPpoWalk-Direct-v0 `
  --headless --num_envs 64 --max_iterations 5
```

※ `` ` `` の直後にスペースを入れないこと。bash の `\` 継続は PowerShell では使えません。

- ログ: `logs/rsl_rl/biped_ppo_walk/<run>/`（Direct） / `logs/rsl_rl/biped_ppo_walk_manager/<run>/`（Manager-Based）
- WandB: デフォルトオンライン（`--wandb_mode offline` でローカルのみ）
- GUI で学習中の映像を見続けるのは重いので、**学習は `--headless`、確認は後述の `play.py`** を推奨

### WandB の監視ダッシュボード

重要指標は学習側が `0_Watchlist/*` セクションに重複ログする（Manager-Based 版
`biped_ppo_walk_env.py` の `_log_watchlist()`）。WandB の Charts 最上部に自動表示される。

Workspace（監視ビュー）と Report（指標の見方ガイド）はスクリプトで生成できる:

```powershell
# Workspace + Report を両方作成（wandb login 済みであること）
python scripts/wandb_dashboard.py

# 片方だけ
python scripts/wandb_dashboard.py --workspace-only
python scripts/wandb_dashboard.py --report-only
```

実行するたびに新しい Saved View / Report が追加されるので、作り直した場合は
WandB UI で古い方を削除する。Isaac Sim 不要（純 WandB API）。

## Manager-Based スクリプト（薄いラッパー）

Direct 版と同一の train/play/eval 本体を、Manager-Based タスク既定値で起動する:

```powershell
python scripts/manager_based/train.py --headless --num_envs 64 --max_iterations 5
python scripts/manager_based/play.py --load_run 2026-07-19_04-52-15
python scripts/manager_based/eval.py --load_run 2026-07-19_04-52-15
python scripts/manager_based/smoke.py --num_envs 4 --steps 200
```

## 評価・再生

GUI でロボットの動きを見るのは基本 **`play.py`**（Play タスク）です。  
運用の型は **headless で学習 → 節目で play / eval → 必要なら `--resume` で再開** です。

### `--load_run`（run ディレクトリ名）

学習 1 回ごとに日時名のフォルダが作られます。`--load_run` には **フルパスではなく、そのフォルダ名だけ** を渡します。

```
logs/rsl_rl/biped_ppo_walk_manager/          # Manager-Based
├── 2026-07-19_04-52-15/                     # ← これが run_dir_name
│   ├── model_0.pt
│   ├── model_10.pt
│   └── model_20.pt
└── 2026-07-18_18-39-55/

logs/rsl_rl/biped_ppo_walk/                  # Direct
└── 2026-07-05_11-11-18/
```

```powershell
# ○ 正しい（フォルダ名のみ）
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-Play-v0 --load_run 2026-07-19_04-52-15

# × 誤り（フルパスは渡さない）
# --load_run Z:\Projects\yuuki-lab\isaac-lab\logs\rsl_rl\biped_ppo_walk_manager\2026-07-19_04-52-15
```

一覧確認の例:

```powershell
Get-ChildItem logs\rsl_rl\biped_ppo_walk_manager
```

### どのチェックポイントが読まれるか

| 指定 | 選ばれるもの |
|------|----------------|
| `--load_run 2026-07-19_04-52-15` のみ | その run 内の **最新** `model_*.pt`（上例なら `model_20.pt`） |
| `--load_run` / `--checkpoint` とも省略 | **最新 run** の **最新** `model_*.pt` |
| `--checkpoint <フルパス>` | 指定ファイルをそのまま読む（`--load_run` は使われない） |

実際に読んだパスは起動ログの次の行で確認できます。

```
[INFO]: Loading model checkpoint from: ...\2026-07-19_04-52-15\model_20.pt
```

途中イテレーションを見るときは **ファイルのフルパス** を渡します（ファイル名だけ + `--load_run` の併用はこの `play.py` では意図どおりにならないことがあります）。チェックポイントは `save_interval=10` ごと（`model_10.pt`, `model_20.pt`, …）。

```powershell
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-Play-v0 `
  --checkpoint Z:\Projects\yuuki-lab\isaac-lab\logs\rsl_rl\biped_ppo_walk_manager\2026-07-19_04-52-15\model_10.pt
```

### コマンド例

**Direct 版**

```powershell
python scripts/eval_biped_walk.py --load_run 2026-07-19_04-52-15
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-Direct-Play-v0 --load_run 2026-07-19_04-52-15
```

**Manager-Based 版**（タスク ID は末尾 `-v0` まで必要）

```powershell
# 定量評価（headless: 移動距離・エピソード長・片脚率）
python scripts/eval_biped_walk.py --task YuukiLab-BipedPpoWalk-v0 --load_run 2026-07-19_04-52-15

# GUI 再生（Play タスクは 16 env・可視化向け）
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-Play-v0 --load_run 2026-07-19_04-52-15
```

学習の続きから再開する例:

```powershell
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --headless --resume --load_run 2026-07-19_04-52-15
```

## Robotics Hub 連携

学習ログは [robotics-hub/server/isaac_rl_log_server.py](../robotics-hub/server/isaac_rl_log_server.py) 経由で Hub の「Isaac 学習進捗」画面に表示できます。

```powershell
$env:ISAAC_RL_LOG_ROOT = "Z:\\Projects\\yuuki-lab\\isaac-lab\\logs\\rsl_rl"
cd ..\\robotics-hub\\server
python isaac_rl_log_server.py
```

## mujoco-sim との関係

| 項目 | mujoco-sim (exp_030・参照) | isaac-lab（**本線**） |
|------|---------------------------|----------------------|
| 位置づけ | 旧本線・設計背景の参照 | 日常の学習・eval・改善 |
| シミュレータ | MuJoCo | Isaac Sim |
| 報酬・終了条件 | Hydra YAML | `biped_ppo_walk_env_cfg.py` |
| ロボット MJCF | `mujoco_sim_assets/` | `yuuki_isaac_lab/assets/robots/yuuki_biped/` |

モデルは現状コピー運用です。将来 `mujoco_sim_assets` との共有を検討してください。  
**新規の学習・評価は本パッケージ（`isaac-lab/`）で行い、MuJoCo `train.py` は使わないでください。**
