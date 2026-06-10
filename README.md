# yuuki-lab

等身大ロボット製作の動画を公開しているYouTubeチャンネル「ゆうきラボ | Yuuki Lab」の公式リポジトリです。

YouTubeチャンネル　→　https://www.youtube.com/@YuukiLab

動画で使用しているツールのプログラムや製作日記を公開しています。

下のリンクのイシューに製作日記をつけています。

https://github.com/yuuki1645/robotics-notes-public/issues/1

<br>

# 強化学習実験（本線・更新中）

MuJoCo 上の **両脚・交互片脚歩行 PPO** を、いま最も活発に更新しているのが **exp_030** です（2026-06〜）。  
exp_029 の fork で runs を整理し、**Hydra 設定**・**Subproc VecEnv**（並列ロールアウト）・**pytest / GitHub Actions**・**eval 横断比較**まで一通り揃えた本線実験です。

| 項目 | 内容 |
|------|------|
| タスク | 交互片脚歩行（観測 51 次元 `biped_walk_v1`） |
| アルゴリズム | PPO（MLP 256→256→128、exp_026 系を継承） |
| 採点 | 固定プロトコル eval の **`displacement_x_mean`**（前進量） |
| チェックポイント | `mujoco-sim/mujoco_rl_sim/runs/exp_030_biped_ppo_walk/` |

### 導線（読む順・実行の入口）

| 目的 | リンク |
|------|--------|
| **いま触る実験フォルダ** | [mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) |
| **最短手順（README 入口）** | [exp_030 README](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/README.md) |
| **強化学習の学び直し・理論** | [docs/rl/](docs/rl/README.md) — MDP・PPO・報酬設計の一般論 |
| **詳細ドキュメント（正本）** | [docs/experiments/exp_030_biped_ppo_walk/](docs/experiments/exp_030_biped_ppo_walk/README.md) — ワークフロー・報酬・終了条件・コードリーディング |
| **実験ドキュメント一覧** | [docs/experiments/](docs/experiments/README.md) |
| **MuJoCo / RL パッケージ全体** | [mujoco-sim/README.md](mujoco-sim/README.md) |
| **AWS Spot 並列学習** | [aws/README.md](aws/README.md) |
| **AI エージェント向け** | [experiments/AGENTS.md](mujoco-sim/mujoco_rl_sim/experiments/AGENTS.md) / [exp_030 AGENTS.md](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/AGENTS.md) |

```bash
cd mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk
pip install -r requirements.txt
python train.py training=smoke runtime=fast   # スモーク
python train.py runtime=fast                # 本番（既定 5000 updates）
python scripts/eval_compare.py              # run 横断比較
```

直前の系統（参照用）: [exp_029](mujoco-sim/mujoco_rl_sim/experiments/exp_029_biped_ppo_walk/)（コピー元） / [exp_026](mujoco-sim/mujoco_rl_sim/experiments/exp_026_biped_ppo_hop_balance/)（歩行報酬設計の源流）。  
それ以前の片脚ホッパ等は `mujoco-sim/mujoco_rl_sim/experiments/archive/` にあります。

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

実機とつなぐときは、同じリポジトリの **`robot-daemon`** を起動し、ブラウザから API（既定ポート 5000）および必要に応じて Socket.IO（IMU）にアクセスします。**MuJoCo RL 学習**（本線は [exp_030](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) の `train.py`）と併用する場合は、ハブの **「学習テレメトリ」**（`/training-telemetry`）で Socket.IO（既定 **8791**）経由の観測・行動表示が利用できます。`runtime.step_wall_sleep`（Hydra）や `--step-wall-sleep` で壁時計の遅延を調整できます。

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

## ■ mujoco-sim

MuJoCo の脚モデルを **実時間 HTTP サーバ**（`mujoco_realtime_sim`）と **強化学習用環境**（`mujoco_rl_sim`）に分けた Python パッケージ群です。起動例は `python -m mujoco_realtime_sim`。

**強化学習の本線**は [exp_030_biped_ppo_walk](mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/)（詳細は上記 [強化学習実験](#強化学習実験本線更新中) 節）。各 RL 実験の `train.py` では **Socket.IO テレメトリ**（既定ポート **8791**）や壁時計遅延が選べます。**robotics-hub** の学習テレメトリ画面（`/training-telemetry`）と連携する手順は [mujoco-sim/README.md](mujoco-sim/README.md) を参照してください。

---

※本リポジトリおよびWikiには、Amazonアソシエイトリンクが含まれています。
