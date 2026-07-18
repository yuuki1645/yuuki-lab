# mujoco-sim

このディレクトリは **pip プロジェクト名 `mujoco-sim`**（配布・インストール単位）で、中に **5 つの Python パッケージ**があります。

- **`mujoco_sim_assets`** — **共有 MJCF**（`xmls/`）と `resolved_model_xml()` などのパス解決。実時間シミュも試用スクリプトもここを参照します。
- **`mujoco_sim_common`** — 論理角 kinematics、Hub 向け Socket.IO テレメトリ、ビュワー補助 HTTP などの共有部品。
- **`mujoco_realtime_sim`** — 脚 MJCF を **実時間で `mj_step` しながら** Flask HTTP で状態取得・サーボ指令（`robot-daemon` と揃えた API）を受け付ける。
- **`mujoco_rl_sim`** — **PPO 実験**（`experiments/`）と各 exp 内の共有コード。wandb や SB3 サンプル利用時は **`pip install -e ".[rl]"`**。実験の学習には **PyTorch** を別途インストール。
- **`mujoco_biped_control`** — **明示制御** による両脚歩行（非 RL）。[walk_v0](mujoco_biped_control/walk_v0/) が exp_030 と同一 MJCF を使用。

サーバーは起動時にバックグラウンドで `mj_step` を回し続け（`model.opt.timestep` 周期、既定 500 Hz）、HTTP API は **サーボの目標角度（`ctrl`）の更新** を主に担当します。

## 前提

- Python 3.10 以上
- [MuJoCo](https://mujoco.org/) の Python バインディング（`pip install mujoco` で入るもの）

## セットアップ

```bash
cd mujoco-sim
pip install -e .
```

RL 環境や Stable-Baselines3 を使う場合:

```bash
pip install -e ".[rl]"
```

オフスクリーンで MP4 を書き出すサンプル（`programs/mujoco_test_005.py`）を使う場合:

```bash
pip install -e ".[video]"
```

`mujoco_test_005.py` は **データビュワー用フォルダ一式**（`video.mp4` / `imu.csv` / `servo.csv` / `manifest.json`）をカレントに出力します。

依存のみ先に入れる場合:

```bash
pip install -r requirements.txt
```

## HTTP サーバーの起動

```bash
python -m mujoco_realtime_sim
```

既定では **`0.0.0.0:8787`** で HTTP を待ち受けると同時に **MuJoCo パッシブ Viewer** が開きます（ポーズエディタからの指令と同一シミュをその場で表示）。Viewer を出したくないときは **`--no-viewer`** を付けます。

同一 PC のみに限定したいときは `--host 127.0.0.1` を付けてください。インストール後は **`mujoco-sim-serve`** でも同じ処理を起動できます。

### オプション

| オプション | 説明 |
|------------|------|
| `--host` | バインドアドレス（既定: `0.0.0.0`。localhost のみなら `127.0.0.1`） |
| `--port` | ポート（既定: `8787`） |
| `--xml PATH` | 使用する MJCF。`MUJOCO_REALTIME_SIM_XML` と `MUJOCO_SIM_XML` の両方に反映（後方互換） |
| `--quiet-http` | Werkzeug のアクセス行だけ抑える（`mujoco_realtime_sim.api` の受信ログはそのまま） |
| `--no-viewer` | Viewer を出さず **HTTP のみ** |
| `--no-auto-step` | サーバー側の常時 `mj_step` を行わない |

### ログ

- **`werkzeug`**: HTTP アクセス行。`--quiet-http` で抑制。
- **`mujoco_realtime_sim.api`**: `/health`・`/api/*` ごとのリクエストログ。
- **`mujoco_realtime_sim.realtime`**: 実時間ステッパの起動・例外。

### トラブルシュート（ブラウザで「Failed to fetch」）

1. **mujoco-sim が起動しているか**（`python -m mujoco_realtime_sim`）。
2. **ファイアウォール**で TCP **8787** がブロックされていないか。
3. **別端末から robotics-hub を開いている場合**、`VITE_MUJOCO_SIM_URL` で正しい `http://IP:8787` を指定する。

### 環境変数（MJCF）

| 名前 | 説明 |
|------|------|
| `MUJOCO_REALTIME_SIM_XML` | メイン MJCF へのパス（推奨） |
| `MUJOCO_SIM_XML` | 同上（後方互換。未設定で上記も無いときは `mujoco_sim_assets/xmls/001_leg_default/main.xml`） |

### Viewer と HTTP・実時間ステッパ（既定）

- バックグラウンドが **常時 `mj_step`**、Viewer は同一 `MjData` を約 60 Hz で表示。
- **Viewer なし**: `python -m mujoco_realtime_sim --no-viewer`
- **常時ステップ無効**: `python -m mujoco_realtime_sim --no-auto-step`

## Viewer のみ（HTTP なし）

```bash
python -m mujoco_realtime_sim.viewer_cmd
```

`mujoco-sim-view` でも起動できます。

## オフスクリーン動画化（`programs/mujoco_test_005.py`）

`mujoco.Renderer` でシミュレーションをレンダリングし、**MP4** に保存するサンプルです（パッシブ Viewer は開きません）。

**依存（初回のみ）:**

```bash
cd mujoco-sim
pip install -e ".[video]"
```

（または `pip install imageio imageio-ffmpeg`）

**実行例:**

```bash
cd mujoco-sim/programs
python mujoco_test_005.py --dataset YuukiLab004 --steps 3000 --subsample 8
```

カレントディレクトリに `YuukiLab004/` ができ、その中に `video.mp4`・`imu.csv`・`servo.csv`（ヘッダのみ）・`manifest.json`（`acquisition: mujoco`）が入ります。フォルダ名は **`--dataset`**（既定 `MujocoSimExport`）。英数字と `._-` のみ。

- 動画に取り込んだ各フレーム直後の `sensordata` を **`imu.csv`** に記録（Hub 互換列 + `sim_time_s`, `frame_index`, `mj_step`）。加速度は **m/s²**、ジャイロは **rad/s**。
- Hub で使うときは **`robotics-hub/public/data-viewer-datasets/<id>/`** にフォルダごとコピーし、`src/features/data-viewer/dataViewerDatasets.json` に `id` を追加する。
- `--subsample` を省略（`0`）のときは、`--fps`（既定 `30`）と MJCF の `timestep` から間引きを自動計算します。
- `--xml` で MJCF、`--width` / `--height` で解像度、`--camera` で MJCF 内カメラ id（`-1` で既定）を指定できます。詳細は `python mujoco_test_005.py --help`。

## 強化学習（`mujoco_rl_sim`）

> **リポジトリ全体の RL 本線は [Isaac Lab](../isaac-lab/README.md) に移りました。**  
> 本パッケージの RL 実験は **参照・レガシー** です。新規の学習・評価は `isaac-lab/` で行ってください。

MuJoCo 側の最終歩行実験は **`exp_030_biped_ppo_walk`**。系統としては `exp_015_*` 以降（PPO）がアクティブ系で、exp_001〜014 は **`experiments/archive/`**。各実験は **実験専用 MJCF**（`model/main.xml`）と **PyTorch PPO** を持ち、HTTP 実時間シミュ（`8787`）とは別プロセスです。

**依存:**

```bash
pip install -e ".[rl]"   # gymnasium, stable-baselines3, wandb, flask-socketio 等
pip install torch        # 実験の PPO 学習に必須（pyproject には含めていない）
```

| 実験 | 概要 | 詳細 |
|------|------|------|
| **`exp_030`** | 両脚歩行 PPO（MuJoCo 最終系統） | [exp_030 README](mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/README.md) |
| `exp_027`〜`exp_029` | 両脚歩行 PPO（先行） | [exp_029 README](mujoco_rl_sim/experiments/exp_029_biped_ppo_walk/README.md) 等 |
| `exp_018`〜`exp_026` | 両脚ホップ/バランス PPO | [exp_026 README](mujoco_rl_sim/experiments/exp_026_biped_ppo_hop_balance/README.md) 等 |
| `exp_015`〜`exp_017` | 片脚ホッパ PPO | [exp_015 README](mujoco_rl_sim/experiments/exp_015_2joint_ppo_hop_cycle/README.md) 等 |
| `archive/exp_001`〜`exp_014` | 早期 A2C/PPO 実験 | [archive README](mujoco_rl_sim/experiments/archive/README.md) |

**実行例**（参照用。`exp_030_biped_ppo_walk` をカレントに）:

```bash
python train.py
python visualize.py --checkpoint ../../runs/exp_030_biped_ppo_walk/run_YYYYMMDD_HHMMSS/final.pt
```

MuJoCo 内で新 exp を派生する場合は **exp_030 をコピーしてリネーム**する手順が各 README にあります（`package_meta.py` で wandb 名・チェックポイント先を自動決定）。日常の学習は Isaac Lab を使ってください。

**Hub 学習テレメトリ:** 各 exp の `train.py` が Socket.IO（既定 **8791**）を起動。`--step-wall-sleep` で壁時計遅延を調整。

**SB3 の最小サンプル**（Gymnasium + PPO）は `programs/mujoco_test_006.py` / `007.py` を参照（`pip install -e ".[rl]"`）。

**共有コード:** 論理角等は **`mujoco_sim_common/`**。各 exp 内に **`lib/`**・**`telemetry/`**（`RlTelemetryWrapper` 等）を同梱。`programs/mujoco_test_004.py` 等で Hub 向け Socket.IO テレメトリを試用可能。

## HTTP API（要約）

すべて JSON。エラー時は HTTP 400 と `{"error": "..."}`（`/api/step` は 410 で廃止）。

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/health` | 生存確認 |
| GET | `/api/meta` | MJCF パス、アクチュエータ名、`timestep`、ステッパ状態、論理角メタ |
| GET | `/api/state` | 現在状態（`logical_deg` 等） |
| POST | `/api/reset` | リセット後に状態を返す |
| POST | `/api/set` | 単一サーボ（`robot-daemon` の `/set` 同形） |
| POST | `/api/set_multiple` | 複数サーボ一括 |
| PUT | `/api/ctrl` | ctrl 一括 |
| POST | `/api/pause` / `/api/resume` | 実時間ステッパの一時停止・再開 |

`mode` は `"rad"`（既定）・`"deg"`・`"logical"`。論理角は **`mujoco_sim_common/kinematics.py`** の `KINEMATICS` で MuJoCo 関節角に写像します（`mujoco_realtime_sim/app.py` から利用）。

## ディレクトリ構成（概要）

```
mujoco-sim/
  mujoco_sim_assets/
    paths.py           # 既定 MJCF パス・環境変数解決
    xmls/              # MJCF 世代別（既定は 001_leg_default/）
      001_leg_default/ # 胴固定（root freejoint なし）
      002_leg_freejoint/ # 001 と同構成 + root に freejoint
  mujoco_realtime_sim/
    __main__.py        # HTTP + オプション Viewer
    app.py             # Flask create_app()（ログ名 mujoco_realtime_sim.api）
    core.py            # Simulation（MjModel / MjData）
    realtime.py        # 実時間 mj_step スレッド
    passive_viewer.py
    viewer_cmd.py
  mujoco_sim_common/
    kinematics.py      # 論理角⇄MuJoCo 角（実時間・RL で共有）
    telemetry/         # Hub 向け Socket.IO（HubTelemetrySocketIoServer）
    viewer_aux_bridge.py  # ビュワー補助 HTTP（programs/mujoco_test_009.py）
  mujoco_rl_sim/
    experiments/       # PPO 実験（参照・レガシー。リポジトリ本線は ../isaac-lab/）
    runs/              # チェックポイント（git 対象外。archive 実験は runs/archive/）
  pyproject.toml
  requirements.txt
```

## 備考

- Gunicorn 等では **`mujoco_realtime_sim.app:create_app`** を指定。
- `robotics-hub`・`robot-daemon` とは **別プロセス**（ハブは実時間シムに対して主に HTTP を利用。RL 学習テレメトリは学習プロセスの Socket.IO を別途利用）。
