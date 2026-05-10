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

既定では **`127.0.0.1:8787`** で待ち受けます。インストール後は `mujoco-sim-serve` でも同じ処理を起動できます。

### オプション

| オプション | 説明 |
|------------|------|
| `--host` | バインドアドレス（既定: `127.0.0.1`） |
| `--port` | ポート（既定: `8787`） |
| `--xml PATH` | 使用する MJCF（メイン XML）。環境変数 `MUJOCO_SIM_XML` と同じ効果 |
| `--access-log` | Werkzeug の HTTP アクセスログを表示する（既定はエラーのみ） |

LAN からアクセスさせる例:

```bash
python -m mujoco_sim --host 0.0.0.0 --port 8787
```

### 環境変数

| 名前 | 説明 |
|------|------|
| `MUJOCO_SIM_XML` | メイン MJCF へのパス。未設定時はパッケージ内の `xmls/main.xml` |

## Viewer のみ（HTTP なし）

MuJoCo のパッシブ Viewer でモデルを表示し、物理ステップのみ回します。

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
