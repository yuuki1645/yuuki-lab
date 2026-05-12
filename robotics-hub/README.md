# Robotics Hub

複数のロボット用フロントエンドツールを **1 つの Vite + React + TypeScript アプリ** にまとめたポータルです。上部ナビでツールを切り替えます。

**履歴について:** かつてリポジトリ直下にあったスタンドアロンプロジェクト（`leg-servo-tuner` / `leg-servo-tuner-react` / `motion-editor-react` / `motion-editor-react-ts`）は、本ハブへの統合後に**ディレクトリごと削除**しました。旧ソースが必要なときは Git の過去コミットを参照してください（ルート [README.md](../README.md) にも記載）。

現在同梱:

- **モーションエディタ** — タイムライン・キーフレーム編集（旧スタンドアロン `motion-editor-react-ts` 系から統合）
- **レッグサーボ調整** — 脚サーボを 1 本ずつ論理／物理角で調整（旧 `leg-servo-tuner` / `leg-servo-tuner-react` 相当）
- **ポーズエディタ** — メモ風スケッチで脚関節をドラッグし論理角を編集
- **Daemon Socket Test** — `robot-daemon` との Socket.IO（主に IMU）およびサーボ REST の確認用
- **テレメトリ** — 学習時は `train_002_full_actuators` の Socket.IO（観測・行動）に加え、`robot-daemon` の実機 IMU（`imu/sample`）を同一ページで表示

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

**テレメトリページについて:** 学習ストリームの接続先は `getTrainingTelemetrySocketUrl()`（`src/shared/constants.ts`）。既定は **`http://<ブラウザの hostname>:8791`**（`train_002_full_actuators` の `--telemetry-port`）。別マシンで学習するときは **`VITE_TELEMETRY_SOCKET_URL`**（旧: `VITE_RL_TELEMETRY_SOCKET_URL`）を指定してください。実機 IMU は既定で **`http://<hostname>:5000`**（`SERVO_DAEMON_URL` と同じ）へ接続し、接続後に自動で `imu/start` を送ります。IMU だけ別ホストにしたい場合は **`VITE_TELEMETRY_IMU_SOCKET_URL`** を使います。ブックマーク用に **`/rl-telemetry`** は **`/telemetry`** へリダイレクトされます。

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

## 新しいツールを追加する手順

1. **`src/features/<ツールID>/`** にページ用コンポーネントを実装する（例: `MyToolPage.tsx` を default export）。
2. **`src/app/hubTools.tsx`** の `hubTools` 配列にエントリを 1 つ追加する。
   - `lazy(() => import("…"))` で遅延読み込みすると、初回バンドルが膨らみにくいです。
3. サーボ API や定数が必要なら **`src/shared/`**（`api/`・`constants.ts`・`hooks/useServos.ts` 等）を再利用する。

パスは `path` で一意にし、他ツールと被らないようにしてください。

## ディレクトリ構成（概要）

```
src/
  app/           # ハブシェル・ルート定義・ツール一覧（hubTools.tsx）
  shared/        # 複数ツール共通（servo API・型・定数・hooks・テレメトリ用 hooks 等）
  features/      # ツール別（motion-editor, leg-servo-tuner, telemetry, …）
```
