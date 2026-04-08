# iphone-camera-relay

Windows PC 上で Web サーバーを起動し、同一 LAN 内の **iPhone** からブラウザで接続して **カメラ映像をリアルタイム送信**し、**PC 側のブラウザで受信表示**するための最小構成アプリです。

- **技術スタック**: TypeScript、React（Vite）、Express、Socket.IO
- **通信**: JPEG フレームを WebSocket（Socket.IO）経由で中継

## 前提条件

- [Node.js](https://nodejs.org/)（LTS 推奨）がインストール済みであること
- PC と iPhone が **同じ Wi‑Fi（LAN）** にいること
- **iPhone でカメラを使う場合は HTTPS が必須**です（後述）

## セットアップ

リポジトリ内のこのフォルダをカレントにして依存関係を入れます。

```bash
cd iphone-camera-relay
npm install
```

## 起動方法

### 開発モード（ホットリロード）

```bash
npm run dev
```

- 既定で **`https` または `http` のどちらか**で待ち受けます（証明書の有無で自動切替）。
- 既定ポートは **`5000`**。変更する場合は環境変数 `PORT` を指定してください。

```bash
# Windows (PowerShell)
$env:PORT="5010"; npm run dev

# または cross-env 経由で npm scripts 内と同様に指定可能
```

### 本番ビルド後の起動

```bash
npm run build
npm start
```

ビルド結果は `dist/client`（フロント）と `dist/server`（サーバー）に出力されます。

## アクセス URL

PC の **LAN 上の IP アドレス**（例: `192.168.1.10`）を確認し、次のように開きます。

| 用途 | パス | 例 |
|------|------|-----|
| 案内ページ | `/` | `https://192.168.1.10:5000/` |
| **iPhone（送信・カメラ）** | `/camera` | `https://192.168.1.10:5000/camera` |
| **PC（受信・モニター）** | `/monitor` | `https://192.168.1.10:5000/monitor` |

- サーバーは **`0.0.0.0`** で待受けるため、同一 LAN から PC の IP で到達できます。
- Windows ファイアウォールで Node がブロックされている場合は、**プライベートネットワーク向けに許可**するか、使用ポートを開けてください。

## HTTPS（cert.pem / key.pem）

iPhone の Safari / Chrome（iOS 上は WebKit ベース）は、**LAN の `http://` ではカメラ API が使えません**。カメラを使うには **`https://` で開く**必要があります。

このフォルダの **直下**（`package.json` と同じ階層）に次の 2 ファイルを置くと、サーバーは **HTTPS** で起動します。

- `cert.pem` … 証明書（公開側）
- `key.pem` … 秘密鍵（**第三者に渡さない・Git に含めない**）

どちらも **PEM 形式**のテキストファイルです。ファイルが無い場合は **HTTP** で起動します（PC のモニター確認程度は可能ですが、**iPhone カメラは原則不可**）。

### 自己署名証明書の例（OpenSSL）

開発・LAN 限定用途の例です。コマンドは環境により `openssl` のパスが異なります。

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

- ブラウザには「信頼できない証明書」と表示されることがあります。**開発用として続行**し、必要に応じて端末側で信頼設定を行ってください。
- **本番・不特定多数向け**には Let's Encrypt など適切な CA で取得した証明書の利用を検討してください。

### mkcert を使う場合（開発向け）

[mkcert](https://github.com/FiloSottile/mkcert) でローカル用の信頼済み証明書を作る方法もあります。生成されたファイルを `cert.pem` / `key.pem` としてコピーしても構いません（ツールの出力ファイル名に合わせてリネーム）。

## 動作の流れ

1. iPhone で `/camera` を開き、「開始」でカメラを起動すると、一定間隔で JPEG フレームが Socket.IO でサーバーに送信されます。
2. サーバーは最新フレームを保持し、**送信元以外**の接続（モニター）へ `frame_update` で配信します。
3. PC で `/monitor` を開くと、受信した JPEG を画像として表示します。

## トラブルシューティング

| 現象 | 確認すること |
|------|----------------|
| iPhone でカメラが使えない | **`https://`** で開いているか、`cert.pem` / `key.pem` が置いてあるか |
| 接続できない | PC の IP・ポート、ファイアウォール、同一 Wi‑Fi か |
| PC だけ HTTP で試したい | モニター側は HTTP でも表示できることがありますが、iPhone 送信側は HTTPS 推奨 |

## ライセンス・セキュリティ

- このリポジトリ用途は **同一 LAN 内の検証**を想定しています。インターネットにそのまま公開しないでください。
- **`key.pem` をバージョン管理に含めないでください。**（`.gitignore` で `dist` 等のみの場合、証明書は手元で管理すること）

## npm スクリプト一覧

| コマンド | 説明 |
|----------|------|
| `npm run dev` | 開発サーバー（Vite ミドルウェア + Express + Socket.IO） |
| `npm run build` | クライアントビルド + サーバー TypeScript コンパイル |
| `npm start` | ビルド後の本番起動（`NODE_ENV=production`） |
| `npm run preview` | Vite のプレビュー（本アプリの Socket サーバーとは別。通常は `dev` / `start` を利用） |
