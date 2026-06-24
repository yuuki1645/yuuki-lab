# isaac-lab

[yuuki-lab](https://github.com/yuuki1645/yuuki-lab) 内の **Isaac Lab 拡張**です。  
MuJoCo 本線 [exp_030](../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) を Isaac Sim / Isaac Lab 上で学習するための移植版です。

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

| Task ID | 用途 |
|---------|------|
| `YuukiLab-BipedPpoWalk-Direct-v0` | 学習 |
| `YuukiLab-BipedPpoWalk-Direct-Play-v0` | 再生・録画 |

**タスクの詳細解説**: [source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/direct/biped_ppo_walk/README.md](source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/direct/biped_ppo_walk/README.md)（観測・報酬・終了・exp_030 対応表）

## 学習

**1行で書く（PowerShell / bash 共通・おすすめ）**

```powershell
# スモーク
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 64 --max_iterations 5

# 本番（例）
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 4096
```

**PowerShell で複数行に分ける場合**は行末に **バッククォート `` ` ``**（`\` ではない）:

```powershell
python scripts/rsl_rl/train.py `
  --task YuukiLab-BipedPpoWalk-Direct-v0 `
  --headless --num_envs 64 --max_iterations 5
```

※ `` ` `` の直後にスペースを入れないこと。bash の `\` 継続は PowerShell では使えません。

- ログ: `logs/rsl_rl/biped_ppo_walk/<run>/`
- WandB: デフォルトオンライン（`--wandb_mode offline` でローカルのみ）

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

| 項目 | mujoco-sim (exp_030) | isaac-lab |
|------|----------------------|-----------|
| シミュレータ | MuJoCo | Isaac Sim |
| 報酬・終了条件 | Hydra YAML | `biped_ppo_walk_env_cfg.py` |
| ロボット MJCF | `mujoco_sim_assets/` | `yuuki_isaac_lab/assets/robots/yuuki_biped/` |

モデルは現状コピー運用です。将来 `mujoco_sim_assets` との共有を検討してください。
