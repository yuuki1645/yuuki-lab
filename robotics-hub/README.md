# Robotics Hub

複数のロボット用フロントエンドツールを **1 つの Vite + React + TypeScript アプリ** にまとめたポータルです。上部ナビでツールを切り替えます。

現在同梱:

- **モーションエディタ** — タイムライン・キーフレーム編集（旧 `motion-editor-react-ts`）
- **レッグサーボ調整** — 脚サーボを 1 本ずつ論理／物理角で調整（旧 `leg-servo-tuner-react` の TypeScript 版）
- **ポーズエディタ** — メモ風スケッチで脚関節をドラッグし論理角を編集
- **Daemon Socket Test** — `robot-daemon` との Socket.IO（主に IMU）およびサーボ REST の確認用
- **RL 学習テレメトリ** — `mujoco-sim` の `train_002_full_actuators` 実行中に、Socket.IO で流れる観測（IMU・prev ctrl）と行動を表示（モータ角は **度（°）**、IMU は従来どおり m/s²・rad/s）

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

**RL 学習テレメトリについて:** 接続先は `getRlTelemetrySocketUrl()`（`src/shared/constants.ts`）。既定は **`http://<ブラウザの hostname>:8791`**（学習側の `train_002_full_actuators` が `--telemetry-port` で待ち受ける Socket.IO）。学習を **別マシン**で動かす場合は、ビルド時に **`VITE_RL_TELEMETRY_SOCKET_URL`**（例: `http://192.168.x.x:8791`）を指定してください。学習プロセスの `--no-telemetry` でサーバを出さないときは、このページは接続できません。

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
| `VITE_IMU_SOCKET_URL` | IMU 用 Socket.IO（未設定時は `getMujocoSimUrl()` と同じ） |
| `VITE_RL_TELEMETRY_SOCKET_URL` | PPO 学習テレメトリ用 Socket.IO（未設定時は `http://<hostname>:8791`） |

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
  shared/        # 複数ツール共通（servo API・型・定数・hooks・RL テレメトリ型）
  features/      # ツール別（motion-editor, leg-servo-tuner, rl-training-telemetry, …）
```
