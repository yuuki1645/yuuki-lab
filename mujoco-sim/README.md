# mujoco-sim

MuJoCo で脚ロボモデルを動かすための **Python パッケージ `mujoco_sim`** と、HTTP で状態取得・ステップ実行できる **Flask サーバー**です。MJCF は `mujoco_sim/xmls/` に同梱されています。

## 前提

- Python 3.10 以上
- [MuJoCo](https://mujoco.org/) の Python バインディング（`pip install mujoco` で入るもの）

## セットアップ

```bash
cd mujoco-sim
pip install -e .
```

依存のみ先に入れる場合:

```bash
pip install -r requirements.txt
```

## HTTP サーバーの起動

```bash
python -m mujoco_sim
```

既定では **`0.0.0.0:8787`** で HTTP を待ち受けると同時に **MuJoCo パッシブ Viewer** が開きます（ポーズエディタからの指令と同一シミュをその場で表示）。Viewer を出したくないとき（サーバーだけ・ヘッドレス）は **`--no-viewer`** を付けます。

同一 PC のみに限定したいときは `--host 127.0.0.1` を付けてください。インストール後は `mujoco-sim-serve` でも同じ処理を起動できます。

### オプション

| オプション | 説明 |
|------------|------|
| `--host` | バインドアドレス（既定: `0.0.0.0`。localhost のみなら `127.0.0.1`） |
| `--port` | ポート（既定: `8787`） |
| `--xml PATH` | 使用する MJCF（メイン XML）。環境変数 `MUJOCO_SIM_XML` と同じ効果 |
| `--quiet-http` | Werkzeug のアクセス行だけ抑える（`mujoco_sim.api` の受信ログはそのまま） |
| `--no-viewer` | Viewer を出さず **HTTP のみ**（GUI なしで常駐させたいとき） |

### ログ（フロントから届いているかの確認）

起動時に **`logging.basicConfig`** により、コンソールに INFO が出ます。

- **`werkzeug`**: 標準の HTTP アクセス行（`POST /api/step ... 200` など）。既定で有効。冗長なら `--quiet-http`。
- **`mujoco_sim.api`**: `/health`・`/api/*` ごとに **`GET/POST`・パス・`client=`（接続元 IP）** を出力。`POST /api/step` と `PUT /api/ctrl` では **JSON 本文**も 1 行に載せます（ポーズエディタからの指令確認用）。

### トラブルシュート（ブラウザで「Failed to fetch」）

1. **mujoco-sim が起動しているか**（この PC またはシミュを動かしているマシンで `python -m mujoco_sim`）。
2. **ファイアウォール**で TCP **8787** がブロックされていないか（Windows なら「Python」のプライベートネットワーク許可など）。
3. **別 PC／タブレットから robotics-hub を開いている場合**、ハブは `http://192.168.x.x:5173` のように **シミュ PC と同じ LAN の IP** で開き、mujoco-sim もそのマシンで動かすか、`VITE_MUJOCO_SIM_URL` で正しい `http://IP:8787` を指定する。

### 環境変数

| 名前 | 説明 |
|------|------|
| `MUJOCO_SIM_XML` | メイン MJCF へのパス。未設定時はパッケージ内の `xmls/main.xml` |

### Viewer と HTTP の関係（既定）

- `python -m mujoco_sim` だけなら **Viewer 付き**。ブラウザからの `POST /api/step` で **`mj_step` した姿勢**がウィンドウに反映されます。
- **別プロセス**の `viewer_cmd` は REST と共有しないため、ポーズエディタと見た目を合わせるときは **この既定起動（または同一コードパス）**を使ってください。
- Viewer を閉じると **プロセス全体が終わり** HTTP も止まります。
- **Viewer なし**で HTTP だけにしたいとき: `python -m mujoco_sim --no-viewer`

## Viewer のみ（HTTP なし・単体で物理ステップ）

MuJoCo のパッシブ Viewer でモデルを表示し、Viewer 側ループだけで物理ステップします（REST とは共有しません）。

```bash
python -m mujoco_sim.viewer_cmd
```

インストール後は `mujoco-sim-view` でも起動できます。

## HTTP API

すべて JSON を返します。エラー時は HTTP 400 と `{"error": "..."}` になります。

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/health` | 生存確認 `{"status":"ok"}` |
| GET | `/api/meta` | MJCF のパスとアクチュエータ名一覧 |
| GET | `/api/state` | 現在のシミュ状態（`qpos`, `qvel`, `ctrl`, `hinge_joint_rad`, `sensors` など） |
| POST | `/api/reset` | シミュをリセットしたうえで状態を返す |
| POST | `/api/step` | ボディ例: `{"n": 10, "ctrl": {"left_knee_pitch_motor": -0.2}}`。`n` は 1〜10000、`ctrl` は省略可 |
| PUT | `/api/ctrl` | ボディ例: `{"ctrl": {"left_knee_pitch_motor": -0.2}}`。指令のみ更新（ステップはしない） |

アクチュエータ名は `GET /api/meta` の `actuator_names` を参照してください。

### 動作確認の例

```bash
curl http://127.0.0.1:8787/health
curl http://127.0.0.1:8787/api/meta
curl -X POST http://127.0.0.1:8787/api/step -H "Content-Type: application/json" -d "{\"n\": 5}"
```

## ディレクトリ構成（概要）

```
mujoco-sim/
  mujoco_sim/          # Python パッケージ
    app.py             # Flask create_app()
    core.py            # Simulation（MjModel / MjData）
    xmls/              # MJCF（package-data で配布）
  pyproject.toml
  requirements.txt
```

## 備考

- 開発用には `python -m mujoco_sim` の `app.run` で十分です。本番で Gunicorn 等を使う場合は、アプリケーション工場 **`mujoco_sim.app:create_app`** を指定してください。
- `robotics-hub` や `robot-daemon` とは別プロセスです。連携する場合は別途ブリッジやクライアント側の設定が必要です。
