# mujoco-sim

MuJoCo で脚ロボモデルを動かすための **Python パッケージ `mujoco_sim`** と、それを **実時間ペースで常時シミュレートしながら** 状態取得・サーボ指令を受け付ける **Flask サーバー**です。MJCF は `mujoco_sim/xmls/` に同梱されています。

サーバーは起動時にバックグラウンドで `mj_step` を回し続け（`model.opt.timestep` 周期、既定 500 Hz）、HTTP API は **サーボの目標角度（`ctrl`）の更新だけ** を担当します。これは `robot-daemon` の `/set` / `/set_multiple` と揃えた設計です。

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
| `--no-auto-step` | サーバー側の常時 `mj_step`（実時間ペース）を行わない。状態は `PUT /api/ctrl` 等で書いた直後の姿勢のまま固まる（旧挙動寄り） |

### ログ（フロントから届いているかの確認）

起動時に **`logging.basicConfig`** により、コンソールに INFO が出ます。

- **`werkzeug`**: 標準の HTTP アクセス行（`POST /api/set ... 200` など）。既定で有効。冗長なら `--quiet-http`。
- **`mujoco_sim.api`**: `/health`・`/api/*` ごとに **`GET/POST`・パス・`client=`（接続元 IP）** を出力。`POST /api/set`・`POST /api/set_multiple`・`PUT /api/ctrl` では **JSON 本文** も 1 行に載せます（ポーズエディタからの指令確認用）。
- **`mujoco_sim.realtime`**: 実時間ステッパの起動・例外を 1 行ずつ出します。

### トラブルシュート（ブラウザで「Failed to fetch」）

1. **mujoco-sim が起動しているか**（この PC またはシミュを動かしているマシンで `python -m mujoco_sim`）。
2. **ファイアウォール**で TCP **8787** がブロックされていないか（Windows なら「Python」のプライベートネットワーク許可など）。
3. **別 PC／タブレットから robotics-hub を開いている場合**、ハブは `http://192.168.x.x:5173` のように **シミュ PC と同じ LAN の IP** で開き、mujoco-sim もそのマシンで動かすか、`VITE_MUJOCO_SIM_URL` で正しい `http://IP:8787` を指定する。

### 環境変数

| 名前 | 説明 |
|------|------|
| `MUJOCO_SIM_XML` | メイン MJCF へのパス。未設定時はパッケージ内の `xmls/main.xml` |

### Viewer と HTTP・実時間ステッパの関係（既定）

- `python -m mujoco_sim` だけなら **Viewer 付き**。サーバー内のバックグラウンドスレッドが **常時 `mj_step` を実時間で回し**、Viewer はその同一 `MjData` を 60 Hz で表示します。
- HTTP からは **目標角度の更新（`/api/set` 等）だけ** を行います。物理時間の進行は HTTP の有無に依存しません。
- **別プロセス**の `viewer_cmd` は REST と共有しないため、ポーズエディタと見た目を合わせるときは **この既定起動（または同一コードパス）** を使ってください。
- Viewer を閉じると **プロセス全体が終わり** HTTP も止まります。
- **Viewer なし**で HTTP だけにしたいとき: `python -m mujoco_sim --no-viewer`
- **物理を進めたくない**（旧 `/api/step` 駆動のような挙動が必要）なら: `python -m mujoco_sim --no-auto-step`

## Viewer のみ（HTTP なし・単体で物理ステップ）

MuJoCo のパッシブ Viewer でモデルを表示し、Viewer 側ループだけで物理ステップします（REST とは共有しません）。

```bash
python -m mujoco_sim.viewer_cmd
```

インストール後は `mujoco-sim-view` でも起動できます。

## HTTP API

すべて JSON を返します。エラー時は HTTP 400 と `{"error": "..."}` になります（`/api/step` だけは廃止のため 410）。

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/health` | 生存確認 `{"status":"ok"}` |
| GET | `/api/meta` | MJCF のパス、アクチュエータ名、`timestep`、実時間ステッパの状態 |
| GET | `/api/state` | 現在のシミュ状態（`time`, `qpos`, `qvel`, `ctrl`, `hinge_joint_rad`, `sensors` など） |
| POST | `/api/reset` | シミュをリセットしたうえで状態を返す |
| POST | `/api/set` | **単一サーボ**の目標角度を更新（`robot-daemon` の `/set` と同形）。ボディ: `{actuator, angle, mode?}` |
| POST | `/api/set_multiple` | **複数サーボ**を一括更新（`/set_multiple` と同形）。ボディ: `{angles: {name: angle, ...}, mode?}` |
| PUT | `/api/ctrl` | 低レベルの ctrl 一括書き込み（`/api/set_multiple` と等価。歴史的経路） |
| POST | `/api/pause` | 実時間ステッパを一時停止 |
| POST | `/api/resume` | 実時間ステッパを再開 |
| ~~POST~~ | ~~`/api/step`~~ | **廃止** (HTTP 410)。サーバ側が常時自動でステップするため、外部から step を進める必要はありません。 |

アクチュエータ名は `GET /api/meta` の `actuator_names` を参照してください。

#### 角度の単位（`mode`）

`/api/set`・`/api/set_multiple`・`PUT /api/ctrl` のボディには `"mode"` を付けられます。

| 値 | 意味 |
|------|------|
| `"rad"`（既定） | `angle` / `ctrl` は MuJoCo ネイティブの単位（ラジアン）。 |
| `"deg"` | `angle` / `ctrl` は度。サーバー側で `math.radians` 換算してから適用する。 |

度で送ると `mujoco_sim.api` の JSON ログがそのまま読みやすい数字（例: `12`）になります。
ポーズエディタは `/api/set` を `"deg"` で叩きます。例:

```bash
# 単一: 左膝を 12°
curl -X POST http://127.0.0.1:8787/api/set \
  -H "Content-Type: application/json" \
  -d "{\"actuator\": \"left_knee_pitch_motor\", \"mode\": \"deg\", \"angle\": 12}"

# 複数: 左右の股関節 pitch を同時に
curl -X POST http://127.0.0.1:8787/api/set_multiple \
  -H "Content-Type: application/json" \
  -d "{\"mode\": \"deg\", \"angles\": {\"left_hip_pitch_motor\": 10, \"right_hip_pitch_motor\": -10}}"
```

### 動作確認の例

```bash
curl http://127.0.0.1:8787/health
curl http://127.0.0.1:8787/api/meta
curl http://127.0.0.1:8787/api/state | python -m json.tool   # time が増えているはず
```

## ディレクトリ構成（概要）

```
mujoco-sim/
  mujoco_sim/          # Python パッケージ
    app.py             # Flask create_app()
    core.py            # Simulation（MjModel / MjData）
    realtime.py        # 実時間 mj_step デーモンスレッド
    passive_viewer.py  # サーバ共有の Viewer メインループ
    xmls/              # MJCF（package-data で配布）
  pyproject.toml
  requirements.txt
```

## 備考

- 開発用には `python -m mujoco_sim` の `app.run` で十分です。本番で Gunicorn 等を使う場合は、アプリケーション工場 **`mujoco_sim.app:create_app`** を指定してください。
- `robotics-hub` や `robot-daemon` とは別プロセスです。連携する場合は別途ブリッジやクライアント側の設定が必要です。
