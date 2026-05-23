# mujoco-sim

このディレクトリは **pip プロジェクト名 `mujoco-sim`**（配布・インストール単位）で、中に **4 つの Python パッケージ**があります。

- **`mujoco_sim_assets`** — **共有 MJCF**（`xmls/`）と `resolved_model_xml()` などのパス解決。実時間シミュも試用スクリプトもここを参照します。
- **`mujoco_sim_common`** — 論理角 kinematics、Hub 向け Socket.IO テレメトリ、ビュワー補助 HTTP などの共有部品。
- **`mujoco_realtime_sim`** — 脚 MJCF を **実時間で `mj_step` しながら** Flask HTTP で状態取得・サーボ指令（`robot-daemon` と揃えた API）を受け付ける。
- **`mujoco_rl_sim`** — **A2C 実験**（`experiments/`）と共有 `lib/`（HTTP サーバとは別経路）。wandb や SB3 サンプル利用時は **`pip install -e ".[rl]"`**。実験の学習には **PyTorch** を別途インストール。

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

本番の RL は **`mujoco_rl_sim/experiments/`** 配下の実験パッケージ（2 関節脚 A2C など）で行います。各実験は **実験専用 MJCF**（`model/main.xml`）と **PyTorch 実装の A2C** を持ち、HTTP 実時間シミュ（`8787`）とは別プロセスです。

**依存:**

```bash
pip install -e ".[rl]"   # gymnasium, stable-baselines3, wandb（実験の wandb ログ用）
pip install torch        # 実験の A2C 学習に必須（pyproject には含めていない）
```

| 実験 | 概要 | 詳細 |
|------|------|------|
| `exp_001_2joint_a2c` | 500 Hz 制御・観測 20 次元・姿勢ベース終了 | [README](mujoco_rl_sim/experiments/exp_001_2joint_a2c/README.md) |
| `exp_002_2joint_a2c` | 50 Hz 制御・観測 19 次元・接触終了。ckpt は実験フォルダ内 | [README](mujoco_rl_sim/experiments/exp_002_2joint_a2c/README.md) |
| `exp_003_2joint_a2c` | exp_002 系。ckpt は `mujoco_rl_sim/runs/<実験名>/`（コピー向け） | [README](mujoco_rl_sim/experiments/exp_003_2joint_a2c/README.md) |

**実行例**（いずれも `mujoco-sim` をカレントに）:

```bash
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.train
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.visualize \
  --checkpoint checkpoints/run_YYYYMMDD_HHMMSS/final.pt
```

新規実験は **`exp_003_2joint_a2c` をコピーしてリネーム**する手順が README にあります（`package_meta.py` で wandb 名・チェックポイント先を自動決定）。

**SB3 の最小サンプル**（Gymnasium + PPO）は `programs/mujoco_test_006.py` / `007.py` を参照（`pip install -e ".[rl]"`）。

**共有コード:** `mujoco_rl_sim/lib/`（パス解決・観測正規化など）。`mujoco_rl_sim/telemetry/` には Gymnasium 用 `RlTelemetryWrapper` があります（`mujoco_sim_common.telemetry.HubTelemetrySocketIoServer` へ送出。試用スクリプト `programs/mujoco_test_004.py` などで利用）。

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
    experiments/       # A2C 実験（exp_001_*, exp_002_*, exp_003_* …）
    lib/               # 実験間共有ユーティリティ
    runs/              # exp_003 以降のチェックポイント（git 対象外）
    telemetry/         # Gym ラッパ（RlTelemetryWrapper）
    scripts/           # 試用（test.py など）
  pyproject.toml
  requirements.txt
```

## 備考

- Gunicorn 等では **`mujoco_realtime_sim.app:create_app`** を指定。
- `robotics-hub`・`robot-daemon` とは **別プロセス**（ハブは実時間シムに対して主に HTTP を利用。RL 学習テレメトリは学習プロセスの Socket.IO を別途利用）。
