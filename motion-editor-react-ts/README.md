# motion-editor-react-ts

TypeScript + React（Vite）で実装したモーションエディタです。タイムラインでキーフレームを編集し、リポジトリ直下の **`robot-daemon`** の REST API 経由でサーボを駆動します。

## 前提条件

- **Node.js**（推奨: 現在の LTS）
- 実機やシミュレーションでサーボを動かす場合は、リポジトリ直下の **`robot-daemon`** が起動していること（既定でポート **5000**）

## 依存関係のインストール

プロジェクトディレクトリで次を実行します。

```bash
cd motion-editor-react-ts
npm install
```

## アプリの起動（開発サーバー）

```bash
npm run dev
```

ブラウザで表示される URL（通常は `http://localhost:5173`）を開きます。

LAN 内の別端末からアクセスしたい場合は、ホストを公開して起動できます。

```bash
npx vite --host 0.0.0.0 --port 5173
```

API のベース URL は **`window.location.hostname` とポート 5000** で決まります（`src/constants.ts` の `SERVO_DAEMON_URL`。変数名は従来どおりですが接続先は **robot-daemon**）。開発 PC でフロントと `robot-daemon` を同じマシンで動かしているなら、多くの場合 `http://localhost:5173` で問題ありません。別マシンのブラウザからフロントだけ開く場合は、そのマシンから見えるホスト名で `robot-daemon` に届くよう、ファイアウォールやデーモンの `host` 設定に注意してください。

## 本番ビルドとプレビュー

型チェックとビルド:

```bash
npm run build
```

生成物は `dist/` に出力されます。ビルド結果をローカルで確認する場合:

```bash
npm run preview
```

## リント

```bash
npm run lint
```

## 関連ディレクトリ

- **`robot-daemon/`** … Flask + Flask-SocketIO（サーボは REST の `/servos`, `/set`, `/set_multiple`, `/transition` など）。フロントからは HTTP で接続します。
