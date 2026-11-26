# isaac-lab

[yuuki-lab](https://github.com/yuuki1645/yuuki-lab) 内の **Isaac Lab 拡張**です。  
**リポジトリの強化学習本線**は、カゴと両脚の Manager-Based 歩行 `YuukiLab-BipedWalk-v0` だけです。

仕様の正本は [biped_walk_env_cfg.py](source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/manager_based/biped_walk/biped_walk_env_cfg.py) です。ロボットは [yuuki_legs](source/yuuki_isaac_lab/yuuki_isaac_lab/assets/robots/yuuki_legs/yuuki_legs_cfg.py) の `FUSION_LEGS_CFG` で、形状は Fusion の `BipedAssembly.urdf` を読みます。カゴは地面に固定しません。

改善ループ（AI）: [.cursor/skills/rl-improvement-loop/SKILL.md](../.cursor/skills/rl-improvement-loop/SKILL.md)

## 前提

- [Isaac Lab](https://isaac-sim.github.io/IsaacLab/) と Isaac Sim は **このリポジトリ外** にインストール済みであること
- Python 3.10+（`env_isaaclab` 等の conda 環境を推奨）

## セットアップ

```bash
cd isaac-lab
python -m pip install -e source/yuuki_isaac_lab
```

## タスク

登録される Gym ID は次の2つです。

| Task ID | 用途 |
|---------|------|
| `YuukiLab-BipedWalk-v0` | 学習（既定 4096 env） |
| `YuukiLab-BipedWalk-Play-v0` | 再生（1 env。左スティックで前後を指示） |

物理は 120 Hz、`decimation` は 4 なので、方策は **30 Hz** です。関節の行動は直立姿勢からの位置差分で、係数は 0.25 rad です。

一覧:

```bash
python scripts/list_envs.py --headless
```

## 起動確認

学習はしません。リセット、観測、数ステップだけを見ます。

```powershell
python scripts/smoke_biped_walk.py
```

## 学習

学習中の映像は重いので、学習は `--headless`、動きの確認は `play.py` です。

```powershell
# 学習ループの短い確認
python scripts/rsl_rl/train.py --task YuukiLab-BipedWalk-v0 --headless --num_envs 64 --max_iterations 5

# 本番（環境数の既定は 4096）
python scripts/rsl_rl/train.py --task YuukiLab-BipedWalk-v0 --headless
```

PowerShell で複数行に分けるときは、行末の **バッククォート `` ` ``** を使います。直後にスペースは入れません。

- ログ: `logs/rsl_rl/yuuki_biped_walk/<run>/`
- W&B プロジェクト: `yuuki_biped_walk`
- チェックポイント間隔: `save_interval=50`

## 再生

`--load_run` には、ログフォルダの **ディレクトリ名だけ** を渡します。

```powershell
python scripts/rsl_rl/play.py --task YuukiLab-BipedWalk-Play-v0 --load_run <run_dir_name> --device cpu
```

少数環境の再生は `--device cpu` にします。GPU PhysX はステップごとの固定待ちがあり、1 環境では往復が支配的になります。学習（多数環境・headless）は GPU のままです。

| 指定 | 読まれるチェックポイント |
|------|--------------------------|
| `--load_run <名前>` のみ | その run の最新 `model_*.pt` |
| `--load_run` も `--checkpoint` も省略 | 最新 run の最新 `model_*.pt` |
| `--checkpoint <フルパス>` | そのファイル |

学習を続ける例:

```powershell
python scripts/rsl_rl/train.py --task YuukiLab-BipedWalk-v0 --headless --resume --load_run <run_dir_name>
```

長時間の録画は、fps を制御周期から計算します。

```powershell
python scripts/rsl_rl/record_biped_youtube.py --task YuukiLab-BipedWalk-Play-v0 --load_run <run_dir_name>
```

## ゲームパッドで踵を動かす

歩行の学習とは別です。手順は [docs/heel_teleop.md](../docs/heel_teleop.md) です。

```powershell
python .\scripts\manual_heel_teleop.py "--kit_args=--/app/vulkan=false"
```

## Robotics Hub 連携

学習ログは [robotics-hub/server/isaac_rl_log_server.py](../robotics-hub/server/isaac_rl_log_server.py) 経由で Hub の「Isaac 学習進捗」に出ます。実験名は `yuuki_biped_walk` です。

```powershell
$env:ISAAC_RL_LOG_ROOT = "Z:\\Projects\\yuuki-lab\\isaac-lab\\logs\\rsl_rl"
cd ..\\robotics-hub\\server
python isaac_rl_log_server.py
```

## MuJoCo との関係

MuJoCo の [exp_030](../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) は、以前の歩行実験です。このタスクの報酬・観測・ロボットの仕様ではありません。新規の学習は `YuukiLab-BipedWalk-v0` で行います。
