# Robotics Hub

複数のロボット用フロントエンドツールを **1 つの Vite + React + TypeScript アプリ** にまとめたポータルです。上部ナビでツールを切り替えます。

現在同梱:

- **モーションエディタ** — タイムライン・キーフレーム編集（旧 `motion-editor-react-ts`）
- **レッグサーボ調整** — 脚サーボを 1 本ずつ論理／物理角で調整（旧 `leg-servo-tuner-react` の TypeScript 版）

## 前提

- Node.js（推奨: 現在の LTS）
- 実機連携時は **`servo-daemon`** を起動（既定ポート **5000**。API のホストはブラウザと同じ `hostname` + `:5000` を使用）

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

**`servo-daemon` について:** API のベース URL は **`window.location.hostname` + `:5000`**（`src/shared/constants.ts` の `SERVO_DAEMON_URL`）です。タブレットなどから `http://192.168.x.x:5173` で開いた場合、フロントからは `http://192.168.x.x:5000` にリクエストが飛びます。デーモンを動かしているマシンとポート 5000 が、他端末から届くようにファイアウォールで許可されているか確認してください（デーモンとハブを同一 PC で動かしているのが最も単純です）。

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
  shared/        # 複数ツール共通（servo API・型・定数・hooks）
  features/      # ツール別（motion-editor, leg-servo-tuner, …）
```
