# yuuki-lab

等身大ロボット製作の動画を公開しているYouTubeチャンネル「ゆうきラボ | Yuuki Lab」の公式リポジトリです。

YouTubeチャンネル　→　https://www.youtube.com/@YuukiLab

動画で使用しているツールのプログラムや製作日記を公開しています。

下のリンクのイシューに製作日記をつけています。

https://github.com/yuuki1645/robotics-notes-public/issues/1

<br>

# 強化学習実験（本線・更新中）

**本線は Isaac Lab** 上の **両脚・交互片脚歩行 PPO** です（`isaac-lab/`）。  
MuJoCo の [exp_030](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) から移植した系統で、報酬設計の背景参照は MuJoCo docs に残しています。日常の学習・評価・改善ループは **Isaac のみ** で行います。

| 項目 | 内容 |
|------|------|
| シミュレータ | Isaac Sim / [Isaac Lab](https://isaac-sim.github.io/IsaacLab/) |
| タスク | `YuukiLab-BipedPpoWalk-Direct-v0`（Manager-Based: `YuukiLab-BipedPpoWalk-v0`） |
| アルゴリズム | PPO（RSL-RL） |
| 採点 | `eval_biped_walk.py` の前進量・成功率（例: Success rate ≥ 5 m） |
| チェックポイント | `isaac-lab/logs/rsl_rl/biped_ppo_walk/` |

### 導線（読む順・実行の入口）

| 目的 | リンク |
|------|--------|
| **いま触るパッケージ** | [isaac-lab/](isaac-lab/) |
| **最短手順（README 入口）** | [isaac-lab/README.md](isaac-lab/README.md) |
| **実験ドキュメント（正本）** | [docs/experiments/isaac_biped_ppo_walk/](docs/experiments/isaac_biped_ppo_walk/README.md) — 目的・iterations・eval |
| **タスク詳細（Direct）** | [biped_ppo_walk README](isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/direct/biped_ppo_walk/README.md) |
| **強化学習の学び直し・理論** | [docs/rl/](docs/rl/README.md) — MDP・PPO・報酬設計の一般論 |
| **実験ドキュメント一覧** | [docs/experiments/](docs/experiments/README.md) |
| **AI エージェント向け（改善ループ）** | [.cursor/skills/rl-improvement-loop/SKILL.md](.cursor/skills/rl-improvement-loop/SKILL.md) |

```bash
cd isaac-lab
python -m pip install -e source/yuuki_isaac_lab
# スモーク
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 64 --max_iterations 5
# 評価
python scripts/eval_biped_walk.py --load_run <run_dir> --episodes 10 --num_envs 64
```

学習ログは **robotics-hub** の「Isaac 学習進捗」（`/isaac-rl-log`）からも参照できます。

### MuJoCo 系統（参照・レガシー）

以前の本線だった MuJoCo 実験です。新規学習の入口ではありません。報酬・終了の設計意図を読むときや、明示制御実験と併用するときに参照します。

| 項目 | 内容 |
|------|------|
| 最終 MuJoCo 歩行実験 | [exp_030_biped_ppo_walk](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) |
| 詳細 docs | [docs/experiments/exp_030_biped_ppo_walk/](docs/experiments/exp_030_biped_ppo_walk/README.md) |
| パッケージ全体 | [mujoco-sim/README.md](mujoco-sim/README.md) |
| AWS Spot（MuJoCo 向け） | [aws/README.md](aws/README.md) |

### 明示制御による歩行（非 RL・並行実験）

RL とは別に、**制御プログラム + AI 改善ループ** 用のパッケージがあります（exp_030 と同一 MuJoCo モデル）。

| 項目 | 内容 |
|------|------|
| パッケージ | [mujoco-sim/mujoco_biped_control/](mujoco-sim/mujoco_biped_control/) |
| 実験 | [walk_v0](mujoco-sim/mujoco_biped_control/walk_v0/) |
| 編集対象 | `controller/walk.py` / `conf/controller.yaml` |
| ログ | `runs/mujoco_biped_control/walk_v0/`（軌道 CSV・incidents・スナップショット） |

```bash
cd mujoco-sim/mujoco_biped_control/walk_v0
pip install -r requirements.txt
python run.py
python replay_incident.py --run-dir ../../runs/mujoco_biped_control/walk_v0/run_YYYYMMDD_HHMMSS --incident-index 0
```

<br>

# ディレクトリ解説

## ■ robotics-hub（メイン）

**フロントエンドの中心となる作業場所です。** モーションエディタ、レッグサーボ調整など複数ツールを 1 つの Vite + React + TypeScript アプリにまとめています。

実機とつなぐときは、同じリポジトリの **`robot-daemon`** を起動し、ブラウザから API（既定ポート 5000）および必要に応じて Socket.IO（IMU）にアクセスします。

- **Isaac Lab 学習** … ハブの **「Isaac 学習進捗」**（`/isaac-rl-log`）で `isaac-lab/logs/rsl_rl/` を参照できます。
- **MuJoCo RL（レガシー）** … [exp_030](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) の `train.py` と併用する場合は **「学習テレメトリ」**（`/training-telemetry`、Socket.IO 既定 **8791**）が利用できます。

詳細は [robotics-hub/README.md](robotics-hub/README.md) を参照してください。

## ■ robot-daemon

ラズパイ上でサーボドライバに指令を出すとともに、IMU データを Socket.IO で配信する **Flask + Flask-SocketIO** のサーバーです（REST はサーボ用）。

**[robotics-hub](robotics-hub/)** からこのデーモンの REST API と Socket.IO を利用します（開発・運用の主経路）。

詳細は [robot-daemon/README.md](robot-daemon/README.md) を参照してください。

## ■ 削除済み：旧スタンドアロンのフロントエンド

次のディレクトリは、**[robotics-hub](robotics-hub/)** へ機能を集約したのち、リポジトリから**削除済み**です（重複メンテナンスの解消のため）。  
当時のソースを参照したい場合は、**該当コミットより前の Git 履歴**を辿ってください。

- `leg-servo-tuner`（Flask 版のレッグサーボ調整）
- `leg-servo-tuner-react`
- `motion-editor-react`
- `motion-editor-react-ts`

上記の役割は **robotics-hub** の **レッグサーボ調整**・**モーションエディタ** 等に引き継がれています。手順の詳細は [robotics-hub/README.md](robotics-hub/README.md) を参照してください。

## ■ （更新停止中）programs

雑多なプログラム置き場。

最近はほぼ使っていない。

## ■ isaac-lab

[Isaac Lab](https://isaac-sim.github.io/IsaacLab/) 上で **両脚歩行 PPO** を学習する拡張です（**強化学習の本線**。詳細は上記 [強化学習実験](#強化学習実験本線更新中) 節）。

| 項目 | 内容 |
|------|------|
| パッケージ | [isaac-lab/](isaac-lab/) |
| タスク | `YuukiLab-BipedPpoWalk-Direct-v0` / `YuukiLab-BipedPpoWalk-v0` |
| 詳細 | [isaac-lab/README.md](isaac-lab/README.md) |

## ■ mujoco-sim

MuJoCo の脚モデルを **実時間 HTTP サーバ**（`mujoco_realtime_sim`）と **強化学習用環境**（`mujoco_rl_sim`）に分けた Python パッケージ群です。起動例は `python -m mujoco_realtime_sim`。

**RL 本線は Isaac Lab** に移りました。MuJoCo 側の最終歩行実験は [exp_030_biped_ppo_walk](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/)（参照・レガシー）。各 RL 実験の `train.py` では **Socket.IO テレメトリ**（既定ポート **8791**）や壁時計遅延が選べます。手順は [mujoco-sim/README.md](mujoco-sim/README.md) を参照してください。

---

※本リポジトリおよびWikiには、Amazonアソシエイトリンクが含まれています。
