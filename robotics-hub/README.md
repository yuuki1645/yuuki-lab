# Robotics Hub

複数のロボット用フロントエンドツールを **1 つの Vite + React + TypeScript アプリ** にまとめたポータルです。上部ナビでツールを切り替えます。

**履歴について:** かつてリポジトリ直下にあったスタンドアロンプロジェクト（`leg-servo-tuner` / `leg-servo-tuner-react` / `motion-editor-react` / `motion-editor-react-ts`）は、本ハブへの統合後に**ディレクトリごと削除**しました。旧ソースが必要なときは Git の過去コミットを参照してください（ルート [README.md](../README.md) にも記載）。

現在同梱:

- **モーションエディタ** — タイムライン・キーフレーム編集。再生先は MuJoCo（旧スタンドアロン `motion-editor-react-ts` 系から統合）
- **ポーズエディタ** — メモ風スケッチで脚関節をドラッグし、論理角を MuJoCo へ送る
- **実機テレメトリ（M5）** — サブ PC の [link/host/lab_debug.py](../link/host/lab_debug.py) が CoreS3 の USB（ver 15）を Socket.IO 既定 :8794 で中継する（`/m5-telemetry`）。10 軸と両足（DF9-40、ATOMS3 Lite スレーブ）が出る。片脚の `rt-usb`（ver 14）を挿したときも同じ画面につながる。HELLO から切断までの実験記録は [link/README.md](../link/README.md) の `storage.yaml`。画面から明示して残す本記録は `atom-rt/data/recordings`。机上の解説は **ATOM 手帳**（正本は [atom-rt/docs/field-manual](../atom-rt/docs/field-manual/)、USB **ver 14**）。機体の基本は [docs/robot_control.md](../docs/robot_control.md)
- **ATOM 机上ラボ** — 机上の ATOM + サーボ **1 本**で校正・単体テスト（`/atom-bench`）。ファームは `rt-usb`。同じ `lab_debug.py`（:8794）につなぐ。Lab のまま **40〜230°**（ファーム可動域）を出し、AS5600 の **生角**・補正・ズレ、INA226 の V/A/W、プロファイル・NVS を確認できる。トポロジは左カラムに常設（どのタブでも配線と磁石が見える）、画面下端には接続・USB ver・モード・PWM・指令角・電源・周期・I2C エラー増分を 20 Hz で更新する固定ステータスバーがある。**ATOM 手帳**もここから開ける（`?tab=profile#manual/nvs` など）
- **学習テレメトリ** — mujoco_rl_sim 学習プロセスの Socket.IO（`/training-telemetry`、既定 :8791）
- **データビュワー** — CSV + 動画の同期表示（`/data-viewer`）。YouTube 紹介用・既存形式。**変更は最小限**
- **ラボデータビュワー** — robot-recorder の実験／take を `format_id` 別サブビュワーで表示（`/lab-data-viewer`）
- **MuJoCo ビュワー補助** — mujoco_test_009 連携（`/mujoco-viewer-aux`、既定 :8788）
- **Isaac 学習進捗** — [isaac-lab](../isaac-lab/) の RSL-RL TensorBoard ログ（`/isaac-rl-log`、API 既定 :8792）
- **実機カメラ** — メインPCの [robot-recorder](../robot-recorder/)（MJPEG ライブ + 実験フォルダへの記録、既定 :8766）（`/live-capture`）

## 前提

- Node.js（推奨: 現在の LTS）
- 機体（M5）は **`npm run dev:m5`**（Hub + [link/host/lab_debug.py](../link/host/lab_debug.py)、Socket.IO 既定 **8794**）。`python atom-rt/tools/lab_debug.py` も同じプロセス
- モーションエディタとポーズエディタの再生先は MuJoCo（既定 :8787）。実機のサーボへは出さない
- 実機カメラ表示時は **`robot-recorder`**（OpenCV・キャプチャデバイス）。Streaming Center 等と同時にデバイスを占有しないこと

## セットアップ

```bash
cd robotics-hub
npm install
```

Recorder 初回:

```bash
cd ../robot-recorder
copy config.example.yaml config.local.yaml
pip install -r requirements.txt
```

## 開発サーバー

```bash
npm run dev
```

ブラウザで表示された URL を開く（通常 `http://localhost:5173`）。トップは既定で **モーションエディタ** へリダイレクトされます。

### 実機実験用（Hub + Recorder 同時起動）

ビデオカメラ監視まで含めて起動する場合:

```bash
cd robotics-hub
npm run dev:lab
```

- Vite を **`--host 0.0.0.0:5173`** で起動（iPad から LAN アクセス可）
- あわせて `../robot-recorder/run.py`（既定 **:8766**）を起動
- iPad では Hub の **実機カメラ**（`/live-capture`）を開く（映像 URL はブラウザの hostname + `:8766`）
- 記録は選択中の実験フォルダ配下の take に保存（詳細は robot-recorder README）

カメラ未接続時は `npm run dev` のみで問題ありません。

### ATOM / M5 用（Hub + lab_debug 同時起動）

実機テレメトリ（M5）を使う場合:

```bash
cd robotics-hub
npm run dev:m5
```

- Vite を **`--host 0.0.0.0:5173`** で起動（iPad から LAN アクセス可）
- あわせて [link/host/lab_debug.py](../link/host/lab_debug.py) を起動（Socket.IO 既定 **:8794**、Tk ウィンドウも開く）。中身は [atom-rt/tools/lab_debug.py](../atom-rt/tools/lab_debug.py) と同じプロセス
- iPad では Hub の **実機テレメトリ（M5）**（`/m5-telemetry`）を開く。機体は CoreS3（USB ver 15）。机上の `rt-usb`（ver 14）も同じ画面につながる
- タイトル横の **ATOM 手帳** は机上の `rt-usb` 用（`#manual/usb` など。正本は [atom-rt/docs/field-manual](../atom-rt/docs/field-manual/)）。機体の基本は [docs/robot_control.md](../docs/robot_control.md)
- パッドで踵を動かすとき、実機は上の `dev:m5`（:8794）のまま [link/host/heel_gamepad.py](../link/host/heel_gamepad.py) を足す。シミュの数値を同じ画面に出す日は `dev:m5` を止めて `npm run dev` と [isaac_hub_bridge.py](../robot_description/isaac_hub_bridge.py)（:8795）にする。手順は [docs/heel_teleop.md](../docs/heel_teleop.md)
- 先に `atom-rt` で `pip install -r tools/requirements.txt` が必要。`:8794` は 1 プロセスだけ

### LAN に公開する（同一ネット内の他端末からアクセス）

開発 PC ですべてのインターフェースにバインドして起動します。

```bash
npx vite --host 0.0.0.0 --port 5173
```

（実機カメラも使うなら上記の **`npm run dev:lab`** の方がまとめて起動できます。）

別端末のブラウザでは、起動ログに出る **Network** の URL（例: `http://192.168.x.x:5173`）を開くか、開発 PC の LAN IP を確認して `http://<そのIP>:5173` でアクセスします。

**テレメトリについて:** 実機は **実機テレメトリ（M5）**（`/m5-telemetry`、CoreS3 の USB を [link/host/lab_debug.py](../link/host/lab_debug.py) が :8794 で中継。片脚の `rt-usb` も同じ口）です。足圧は ATOMS3 Lite からこの画面に出ます。学習は **学習テレメトリ**（`/training-telemetry`）です。M5 画面は iPad から **Windows PC の LAN IP:5173** で開きます。学習ストリームの接続先は `getTrainingTelemetrySocketUrl()`（`src/shared/constants.ts`）。既定は **`http://<ブラウザの hostname>:8791`**（各 exp の `train.py` / `config.TELEMETRY_PORT`）。別マシンで学習するときは **`VITE_TELEMETRY_SOCKET_URL`**（旧: `VITE_RL_TELEMETRY_SOCKET_URL`）を指定してください。旧 URL **`/rl-telemetry`** は学習へリダイレクトされます。

以前のラズパイ制御と Pico の足圧は、いまのファイルからは外してある。コードが要るときは git の履歴を見る。

本番ビルドを LAN 向けにプレビューする場合の例:

```bash
npm run build
npx vite preview --host 0.0.0.0 --port 4173
```

## ビルド・プレビュー

```bash
npm run build
npm run preview
```

### 環境変数（Vite）

| 名前 | 説明 |
|------|------|
| `VITE_MUJOCO_SIM_URL` | 実時間 MuJoCo HTTP シムのベース URL（未設定時は `http://<hostname>:8787`） |
| `VITE_IMU_SOCKET_URL` | ヘッダーの IMU ウィンドウ用 Socket.IO（未設定時は MuJoCo と同じ :8787） |
| `VITE_TELEMETRY_SOCKET_URL` | 学習テレメトリ用 Socket.IO（未設定時は `VITE_RL_TELEMETRY_SOCKET_URL` のあと `http://<hostname>:8791`） |
| `VITE_RL_TELEMETRY_SOCKET_URL` | （非推奨）上記と同用途。`VITE_TELEMETRY_SOCKET_URL` を優先してください |
| `VITE_MUJOCO_VIEWER_AUX_URL` | ビュワー補助 API（未設定時は `http://<hostname>:8788`） |
| `VITE_ISAAC_RL_LOG_API_URL` | Isaac 学習ログ API（未設定時は `http://<hostname>:8792`） |
| `VITE_M5_TELEMETRY_SOCKET_URL` | CoreS3 / 机上 ATOM の `lab_debug.py` 中継 Socket.IO（未設定時は `http://<hostname>:8794`）。入口は [link/host/lab_debug.py](../link/host/lab_debug.py)。iPad は Windows PC の LAN IP で Hub を開く |
| `VITE_CAPTURE_REALTIME_URL` | 実機カメラ MJPEG ベース URL（未設定時は `http://<hostname>:8766`） |

## Isaac 学習進捗（TensorBoard ログ）

[isaac-lab](../isaac-lab/) の RSL-RL 学習ログ（`logs/rsl_rl/<experiment>/<run>/events.out.tfevents.*`）を、Robotics Hub 上でグラフ表示します。**20 秒ごと**に自動更新されます。

**ログルート（既定）:** リポジトリ内 `isaac-lab/logs/rsl_rl`（存在する場合は自動検出）

### 1. ログ API サーバーを起動（学習 PC）

```powershell
cd robotics-hub\server
pip install -r requirements.txt
.\start.ps1
```

または:

```powershell
$env:ISAAC_RL_LOG_ROOT = "Z:\Projects\yuuki-lab\isaac-lab\logs\rsl_rl"
python isaac_rl_log_server.py
```

環境変数（任意）:

| 名前 | 説明 |
|------|------|
| `ISAAC_RL_LOG_ROOT` | TensorBoard ログのルート（未設定時は `yuuki-lab/isaac-lab/logs/rsl_rl` を自動検出） |
| `ISAAC_RL_LOG_PORT` | 待ち受けポート（既定 **8792**） |

### 2. Hub を開く

```bash
cd robotics-hub
npm run dev
```

ナビの **Isaac 学習進捗**（`/isaac-rl-log`）を開き、experiment / run を選びます。

### スマホから Tailscale 経由で見る

1. PC・iPhone 両方で Tailscale を **Connected** にする
2. PC で API サーバー: `cd robotics-hub\server` → `.\start.ps1`  
   起動ログに `Tailscale (外出先スマホ向け): http://100.x.x.x:8792` が出ます
3. PC で Hub: `npx vite --host 0.0.0.0 --port 5173`
4. iPhone Safari で Hub を開く: `http://100.x.x.x:5173/isaac-rl-log`（PC の Tailscale IP）
5. **ログ API URL** に `http://100.x.x.x:8792` を入力 →「URL を保存」  
   （localhost 接続時は画面上部に **Tailscale API** と「この URL を適用」ボタンも表示されます）

同一 LAN 内のみなら LAN IP（例: `http://192.168.x.x:8792`）でも可です。

## 新しいツールを追加する手順

1. **`src/features/<ツールID>/`** にページ用コンポーネントを実装する（例: `MyToolPage.tsx` を default export）。
2. **`src/app/hubTools.tsx`** の `hubTools` 配列にエントリを 1 つ追加する。
   - `lazy(() => import("…"))` で遅延読み込みすると、初回バンドルが膨らみにくいです。
3. 共有の定数や API が必要なら **`src/shared/`**（`api/`・`constants.ts`・`hooks/`）を再利用する。実機の関節は M5 の `:8794`、シミュの関節は MuJoCo の `:8787` です。

パスは `path` で一意にし、他ツールと被らないようにしてください。

## データビュワー用データセット（`public/data-viewer-datasets/`）

- 一覧は **`src/features/data-viewer/dataViewerDatasets.json`** の `id` と、`public/data-viewer-datasets/<id>/` フォルダ名を一致させる。
- 各フォルダに **`imu.csv`** と **`servo.csv`** が必須（サーボ無しでもヘッダのみの `servo.csv` で可）。
- **`manifest.json`**（任意だが推奨）の主なキー:
  - `perf_timestamp_at_video_zero` — 動画 `currentTime=0` に対応する perf 軸（秒）。
  - `video_file` — 動画ファイル名（例: `video.mp4`）。未指定時は `video.mp4` / `session.mp4` / `recording.mp4` を順に探す。
  - **`acquisition`** — `"robot"`（実機・省略時の既定） \| `"mujoco"` \| `"other"`。データビュワーは IMU 列見出しの単位表示などを切り替える。
  - **`schema_version`** — 整数（将来の manifest / CSV 拡張用）。
  - **`acquisition_detail`** — 任意オブジェクト（例: MuJoCo なら `mjcf`, `video_fps`, `imu_accel_unit` 等）。`acquisition` が `"other"` のとき、`imu_accel_column_label` / `imu_gyro_column_label` で列見出しを上書き可能。

MuJoCo からの出力は **`mujoco-sim/programs/mujoco_test_005.py`**（`--dataset <id>`。カレントに `<id>/video.mp4` 等の一式を生成）を `public/data-viewer-datasets/<id>/` にコピーして使う。

## ディレクトリ構成（概要）

```
src/
  app/           # ハブシェル・ルート定義・ツール一覧（hubTools.tsx）
  shared/        # 複数ツール共通（servo API・型・定数・hooks・テレメトリ用 hooks 等）
  features/      # ツール別（motion-editor, pose-editor, m5-telemetry, …）
```
