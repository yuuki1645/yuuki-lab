# Robotics Hub

複数のロボット用フロントエンドツールを **1 つの Vite + React + TypeScript アプリ** にまとめたポータルです。上部ナビでツールを切り替えます。

**履歴について:** かつてリポジトリ直下にあったスタンドアロンプロジェクト（`leg-servo-tuner` / `leg-servo-tuner-react` / `motion-editor-react` / `motion-editor-react-ts`）は、本ハブへの統合後に**ディレクトリごと削除**しました。旧ソースが必要なときは Git の過去コミットを参照してください（ルート [README.md](../README.md) にも記載）。

現在同梱:

- **モーションエディタ** — タイムライン・キーフレーム編集（旧スタンドアロン `motion-editor-react-ts` 系から統合）
- **レッグサーボ調整** — 脚サーボを 1 本ずつ論理／物理角で調整（旧 `leg-servo-tuner` / `leg-servo-tuner-react` 相当）
- **ポーズエディタ** — メモ風スケッチで脚関節をドラッグし論理角を編集
- **Daemon Socket Test** — `robot-daemon` との Socket.IO（主に IMU）およびサーボ REST の確認用
- **実機テレメトリ** — `robot-daemon` の IMU（`/device-telemetry`）
- **学習テレメトリ** — mujoco_rl_sim 学習プロセスの Socket.IO（`/training-telemetry`、既定 :8791）
- **データビュワー** — CSV + 動画の同期表示（`/data-viewer`）
- **MuJoCo ビュワー補助** — mujoco_test_009 連携（`/mujoco-viewer-aux`、既定 :8788）
- **Isaac 学習進捗** — [isaac-lab](../isaac-lab/) の RSL-RL TensorBoard ログ（`/isaac-rl-log`、API 既定 :8792）

## 前提

- Node.js（推奨: 現在の LTS）
- 実機連携時は **`robot-daemon`** を起動（既定ポート **5000**。REST のホストはブラウザと同じ `hostname` + `:5000`。IMU は同一オリジンへの Socket.IO）

## セットアップ

```bash
cd robotics-hub
npm install
```

## 開発サーバー

```bash
npm run dev
```

ブラウザで表示された URL を開く（通常 `http://localhost:5173`）。トップは既定で **モーションエディタ** へリダイレクトされます。

### LAN に公開する（同一ネット内の他端末からアクセス）

開発 PC ですべてのインターフェースにバインドして起動します。

```bash
npx vite --host 0.0.0.0 --port 5173
```

別端末のブラウザでは、起動ログに出る **Network** の URL（例: `http://192.168.x.x:5173`）を開くか、開発 PC の LAN IP を確認して `http://<そのIP>:5173` でアクセスします。

**`robot-daemon` について:** REST・Socket.IO のベース URL は **`window.location.hostname` + `:5000`**（`src/shared/constants.ts` の `SERVO_DAEMON_URL`。名前は歴史的経緯のためそのまま）です。タブレットなどから `http://192.168.x.x:5173` で開いた場合、フロントからは `http://192.168.x.x:5000` にリクエスト・WebSocket 相当の接続が飛びます。デーモンを動かしているマシンとポート 5000 が、他端末から届くようにファイアウォールで許可されているか確認してください（デーモンとハブを同一 PC で動かしているのが最も単純です）。

**テレメトリについて:** 画面上部のナビは **実機テレメトリ**（`/device-telemetry`）と **学習テレメトリ**（`/training-telemetry`）に分かれています。学習ストリームの接続先は `getTrainingTelemetrySocketUrl()`（`src/shared/constants.ts`）。既定は **`http://<ブラウザの hostname>:8791`**（各 exp の `train.py` / `config.TELEMETRY_PORT`）。別マシンで学習するときは **`VITE_TELEMETRY_SOCKET_URL`**（旧: `VITE_RL_TELEMETRY_SOCKET_URL`）を指定してください。実機 IMU は既定で **`http://<hostname>:5000`**（`SERVO_DAEMON_URL` と同じ）へ接続し、接続後に自動で `imu/start` を送ります。IMU だけ別ホストにしたい場合は **`VITE_TELEMETRY_IMU_SOCKET_URL`** を使います。旧 URL **`/telemetry`** は実機へ、**`/rl-telemetry`** は学習へリダイレクトされます。

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
| `VITE_IMU_SOCKET_URL` | IMU 用 Socket.IO（未設定時は `getMujocoSimUrl()` と同じ。Daemon Socket Test 等） |
| `VITE_TELEMETRY_SOCKET_URL` | 学習テレメトリ用 Socket.IO（未設定時は `VITE_RL_TELEMETRY_SOCKET_URL` のあと `http://<hostname>:8791`） |
| `VITE_RL_TELEMETRY_SOCKET_URL` | （非推奨）上記と同用途。`VITE_TELEMETRY_SOCKET_URL` を優先してください |
| `VITE_TELEMETRY_IMU_SOCKET_URL` | テレメトリページの実機 IMU（未設定時は `http://<hostname>:5000`） |
| `VITE_MUJOCO_VIEWER_AUX_URL` | ビュワー補助 API（未設定時は `http://<hostname>:8788`） |
| `VITE_ISAAC_RL_LOG_API_URL` | Isaac 学習ログ API（未設定時は `http://<hostname>:8792`） |

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
3. サーボ API や定数が必要なら **`src/shared/`**（`api/`・`constants.ts`・`hooks/useServos.ts` 等）を再利用する。

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
  features/      # ツール別（motion-editor, leg-servo-tuner, telemetry, …）
```
