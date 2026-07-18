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

**1行で書く（PowerShell / bash 共通・おすすめ）**

```powershell
# スモーク（Direct）
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

## Manager-Based スクリプト（薄いラッパー）

Direct 版と同一の train/play/eval 本体を、Manager-Based タスク既定値で起動する:

```powershell
python scripts/manager_based/train.py --headless --num_envs 64 --max_iterations 5
python scripts/manager_based/play.py --load_run <run_dir_name>
python scripts/manager_based/eval.py --load_run <run_dir_name>
python scripts/manager_based/smoke.py --num_envs 4 --steps 200
```

## 評価・再生

```bash
python scripts/eval_biped_walk.py --load_run <run_dir_name>
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-Direct-Play-v0 --load_run <run_dir_name>
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
