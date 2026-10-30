# iphone-camera-relay

Windows PC 上で Web サーバーを起動し、同一 LAN 内の **iPhone** からブラウザで接続して **カメラ映像をリアルタイム送信**し、**PC 側のブラウザで受信表示**するための最小構成アプリです。

- **技術スタック**: フロント … TypeScript、React（Vite）、Socket.IO クライアント／サーバー … **Python**、[FastAPI](https://fastapi.tiangolo.com/)、[python-socketio](https://github.com/miguelgrinberg/python-socketio)、Uvicorn
- **通信**: JPEG フレームを **Socket.IO**（WebSocket 等をトランスポートに利用）経由で中継

## 前提条件

- [Node.js](https://nodejs.org/)（LTS 推奨）… フロントのビルド用
- **Python 3.10 以降**（3.11+ 推奨）… サーバー実行用
- PC と iPhone が **同じ Wi‑Fi（LAN）** にいること
- **iPhone でカメラを使う場合は HTTPS が必須**です（後述）

## セットアップ

リポジトリ内の **`iphone-camera-relay` フォルダ**をカレントにして、フロントとバックエンドの依存関係を入れます。

```bash
cd iphone-camera-relay
npm install
pip install -r requirements.txt
```

（`pip` の代わりに `python -m pip` でも構いません。仮想環境 `.venv` の利用を推奨します。）

## 起動方法

フロントは **ビルド済みの静的ファイル**（`dist/client`）を Python サーバーが **同一ポート**で配信します。初回・フロント変更後は `npm run build` が必要です。

### 開発モード（バックエンドの自動リロード）

```bash
npm run dev
```

- 実行内容: `npm run build` のあと、**Uvicorn（`reload`）**で `backend` を起動します。
- 既定で **`https` または `http` のどちらか**で待ち受けます（`cert.pem` / `key.pem` の有無で自動切替）。
- 既定ポートは **`5000`**。

```powershell
# Windows (PowerShell) … ポート変更例
$env:PORT="5010"; npm run dev
```

フロントの変更をすぐ反映したい場合は、別ターミナルで `npm run dev:client`（`vite build --watch`）を動かし、保存のたびに再ビルドできます。

### 本番に近い起動

```bash
npm start
```

（内部では `npm run build` 後に `python -m backend` を実行します。）

### Python だけで起動（既にビルド済みの場合）

プロジェクトルート（`iphone-camera-relay`）をカレントに:

```powershell
python -m backend
```

ビルドのみ:

```bash
npm run build
```

成果物は **`dist/client`**（React の静的ファイル）だけです。

## アクセス URL

PC の **LAN 上の IP アドレス**（例: `192.168.1.10`）を確認し、次のように開きます。

| 用途 | パス | 例 |
|------|------|-----|
| 案内ページ | `/` | `https://192.168.1.10:5000/` |
| **iPhone（送信・カメラ）** | `/camera` | `https://192.168.1.10:5000/camera` |
| **PC（受信・モニター）** | `/monitor` | `https://192.168.1.10:5000/monitor` |

- サーバーは **`0.0.0.0`** で待受けるため、同一 LAN から PC の IP で到達できます。
- Windows ファイアウォールで **Python / uvicorn** の待ち受けがブロックされている場合は、**プライベートネットワーク向けに許可**するか、使用ポートを開けてください。

## HTTPS（cert.pem / key.pem）

iPhone の Safari / Chrome（iOS 上は WebKit ベース）は、**LAN の `http://` ではカメラ API が使えません**。カメラを使うには **`https://` で開く**必要があります。

このフォルダの **直下**（`package.json` と同じ階層）に次の 2 ファイルを置くと、サーバーは **HTTPS** で起動します。

- `cert.pem` … 証明書（公開側）
- `key.pem` … 秘密鍵（**第三者に渡さない・Git に含めない**）

どちらも **PEM 形式**のテキストです。ファイルが無い場合は **HTTP** で起動します（PC のモニター確認程度は可能ですが、**iPhone カメラは原則不可**）。

Windows では **[mkcert](https://github.com/FiloSottile/mkcert)** でローカル用証明書を作るのが手軽です。以下は Windows 向けの手順です。

### 1. mkcert をインストール

#### Chocolatey がある場合

PowerShell またはコマンドプロンプトで:

```powershell
choco install mkcert
```

#### Scoop がある場合

```powershell
scoop bucket add extras
scoop install mkcert
```

その他の導入方法は [mkcert の README](https://github.com/FiloSottile/mkcert/blob/master/README.md) を参照してください。

### 2. ローカル CA をインストール

**PowerShell を管理者として起動**して実行します。

```powershell
mkcert -install
```

ローカル用の認証局が Windows の信頼ストアに入ります。権限不足で失敗する場合は、管理者で開き直してください。

### 3. PC の LAN 上 IP を確認する

PowerShell またはコマンドプロンプトで:

```powershell
ipconfig
```

**IPv4 アドレス**（例: `192.168.1.10`）を控えます。

### 4. 証明書を作る

控えた IP を **`192.168.1.10` の部分だけ**実際の値に置き換えて実行します。

```powershell
mkcert 192.168.1.10 localhost 127.0.0.1 ::1
```

`localhost` / `127.0.0.1` / `::1` を一緒に含めておくと、同じ PC 上のブラウザからも使いやすくなります。

### 5. ファイル名をそろえて配置する

生成例（名前は環境により多少異なります）:

```text
192.168.1.10+3.pem
192.168.1.10+3-key.pem
```

これらを **`iphone-camera-relay` フォルダ直下**に置き、次の名前にリネームします。

| 元のファイル（例） | リネーム後 |
|----------------|------------|
| `*.pem`（鍵でないほう） | `cert.pem` |
| `*-key.pem` | `key.pem` |

### 6. 起動する

`iphone-camera-relay` をカレントにして:

```powershell
npm run dev
```

本番寄りの一発起動は `npm start`（事前に `npm run build` が走ります）。既に `dist/client` がある場合は `python -m backend` のみでも構いません。

### 7. アクセス例

- **iPhone**: `https://192.168.1.10:5000/camera`（IP とポートは環境に合わせる）
- **Windows PC**: `https://127.0.0.1:5000/monitor` または `https://192.168.1.10:5000/monitor`

### ハマりやすい点

- **管理者権限**: `mkcert -install` が失敗したら、管理者 PowerShell で再実行する。
- **Windows Defender ファイアウォール**: `python` / **uvicorn** 起動時に許可ダイアログが出たら、**同一 LAN で使うならプライベートネットワークを許可**する。拒否すると iPhone から届かないことがあります。
- **iPhone 側の証明書警告**: 接続先や信頼の仕組みによっては、初回に警告や信頼操作が必要なことがあります。LAN 開発用の構成であることに注意してください。
- **本番・インターネット公開**: Let's Encrypt など、用途に応じた正式な CA の利用を検討してください。

### 最短の流れ（参考）

```powershell
choco install mkcert
mkcert -install
ipconfig
mkcert 192.168.1.10 localhost 127.0.0.1 ::1
```

生成された `*.pem` を `cert.pem` と `key.pem` にリネームして **`iphone-camera-relay` と同じフォルダ**へ置き、`npm run dev` で起動します。

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
- **`cert.pem` / `key.pem` をバージョン管理に含めないでください。**（本リポジトリでは `.gitignore` に記載済みです）

## npm / Python コマンド一覧

| コマンド | 説明 |
|----------|------|
| `npm run dev` | `vite build` のあと **Python**（Uvicorn `reload`）で Socket.IO + 静的配信 |
| `npm run dev:client` | `vite build --watch`（フロント変更のたびに再ビルド） |
| `npm run build` | `vite build` → `dist/client` を生成 |
| `npm start` | `npm run build` 後に `python -m backend` |
| `python -m backend` | プロジェクトルートで実行。**`dist/client` が無いと HTTP 503**（先に `npm run build`） |
| `npm run preview` | Vite 単体のプレビュー（**Socket.IO サーバーなし**。本アプリの動作確認には使わない） |
