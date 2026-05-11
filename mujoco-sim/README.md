# mujoco-sim

このディレクトリは **pip プロジェクト名 `mujoco-sim`**（配布・インストール単位）で、中に **3 つの Python パッケージ**があります。

- **`mujoco_sim_assets`** — **共有 MJCF**（`xmls/`）と `resolved_model_xml()` などのパス解決。実時間シミュも RL もここを参照します。
- **`mujoco_realtime_sim`** — 脚 MJCF を **実時間で `mj_step` しながら** Flask HTTP で状態取得・サーボ指令（`robot-daemon` と揃えた API）を受け付ける。
- **`mujoco_rl_sim`** — **強化学習用の Gymnasium 環境**など（HTTP サーバとは別経路）。利用時は **`pip install -e ".[rl]"`** で `gymnasium` と学習ライブラリを追加。

サーバーは起動時にバックグラウンドで `mj_step` を回し続け（`model.opt.timestep` 周期、既定 500 Hz）、HTTP API は **サーボの目標角度（`ctrl`）の更新** を主に担当します。

## 前提

- Python 3.10 以上
- [MuJoCo](https://mujoco.org/) の Python バインディング（`pip install mujoco` で入るもの）

## セットアップ

```bash
cd mujoco-sim
pip install -e .
```

RL 環境や Stable-Baselines3 を使う場合:

```bash
pip install -e ".[rl]"
```

依存のみ先に入れる場合:

```bash
pip install -r requirements.txt
```

## HTTP サーバーの起動

```bash
python -m mujoco_realtime_sim
```

既定では **`0.0.0.0:8787`** で HTTP を待ち受けると同時に **MuJoCo パッシブ Viewer** が開きます（ポーズエディタからの指令と同一シミュをその場で表示）。Viewer を出したくないときは **`--no-viewer`** を付けます。

同一 PC のみに限定したいときは `--host 127.0.0.1` を付けてください。インストール後は **`mujoco-sim-serve`** でも同じ処理を起動できます。

### オプション

| オプション | 説明 |
|------------|------|
| `--host` | バインドアドレス（既定: `0.0.0.0`。localhost のみなら `127.0.0.1`） |
| `--port` | ポート（既定: `8787`） |
| `--xml PATH` | 使用する MJCF。`MUJOCO_REALTIME_SIM_XML` と `MUJOCO_SIM_XML` の両方に反映（後方互換） |
| `--quiet-http` | Werkzeug のアクセス行だけ抑える（`mujoco_realtime_sim.api` の受信ログはそのまま） |
| `--no-viewer` | Viewer を出さず **HTTP のみ** |
| `--no-auto-step` | サーバー側の常時 `mj_step` を行わない |

### ログ

- **`werkzeug`**: HTTP アクセス行。`--quiet-http` で抑制。
- **`mujoco_realtime_sim.api`**: `/health`・`/api/*` ごとのリクエストログ。
- **`mujoco_realtime_sim.realtime`**: 実時間ステッパの起動・例外。

### トラブルシュート（ブラウザで「Failed to fetch」）

1. **mujoco-sim が起動しているか**（`python -m mujoco_realtime_sim`）。
2. **ファイアウォール**で TCP **8787** がブロックされていないか。
3. **別端末から robotics-hub を開いている場合**、`VITE_MUJOCO_SIM_URL` で正しい `http://IP:8787` を指定する。

### 環境変数（MJCF）

| 名前 | 説明 |
|------|------|
| `MUJOCO_REALTIME_SIM_XML` | メイン MJCF へのパス（推奨） |
| `MUJOCO_SIM_XML` | 同上（後方互換。未設定で上記も無いときは `mujoco_sim_assets/xmls/001_leg_default/main.xml`） |

### Viewer と HTTP・実時間ステッパ（既定）

- バックグラウンドが **常時 `mj_step`**、Viewer は同一 `MjData` を約 60 Hz で表示。
- **Viewer なし**: `python -m mujoco_realtime_sim --no-viewer`
- **常時ステップ無効**: `python -m mujoco_realtime_sim --no-auto-step`

## Viewer のみ（HTTP なし）

```bash
python -m mujoco_realtime_sim.viewer_cmd
```

`mujoco-sim-view` でも起動できます。

## 強化学習（`mujoco_rl_sim`）

例: 同梱 MJCF を使う膝トラッキング環境（MJCF に **`freejoint` の `root` が無い**場合は胴高・転倒終了を簡略化します）。

```python
from mujoco_rl_sim import KneeTrackEnv
from mujoco_rl_sim.envs.env_002_full_actuators import Env002FullActuators

env = KneeTrackEnv()  # xml_path 省略時は各 env ファイル先頭の ``DEFAULT_ENV_MODEL_XML``
all_ctrl = Env002FullActuators()  # 全アクチュエータを同時に指令
```

別 MJCF を使う場合は `KneeTrackEnv(xml_path="...")` のように渡すか、各 env ファイル先頭の ``DEFAULT_ENV_MODEL_XML`` を書き換えてください（HTTP 実時間シミュの既定は引き続き環境変数 ``MUJOCO_REALTIME_SIM_XML`` / ``MUJOCO_SIM_XML`` です）。

`Env002FullActuators`（`env_002_full_actuators.py`）は **position アクチュエータがヒンジ関節のみ**であることを前提にしています。行動・観測の次元は MJCF の `nu` に依存します。

環境実装ファイルは **`env_001_knee_track.py`** のように `env_<連番>_` プレフィックスで並べます（新規追加時は次番号のファイルを `envs/__init__.py` に登録）。

### CLI（膝トラックの PPO サンプル）

`pip install -e ".[rl]"` 後、コンソールから:

| コマンド | 内容 |
|----------|------|
| `mujoco-rl-train-knee` | `KneeTrackEnv` を PPO で学習（既定でライブ Viewer 用子プロセスも起動） |
| `mujoco-rl-watch-knee` | チェックポイント更新に追随して Viewer 表示 |
| `mujoco-rl-play-knee` | 学習済み `ppo_knee_track` を Viewer で再生 |

`python -m` でも同じです。

```bash
python -m mujoco_rl_sim.scripts.train_001_knee_track --help
python -m mujoco_rl_sim.scripts.train_001_knee_track --no-viewer
python -m mujoco_rl_sim.scripts.watch_training_live
python -m mujoco_rl_sim.scripts.play_knee_track --model-base ppo_knee_track
```

### CLI（全アクチュエータ `Env002FullActuators`）

| コマンド | 内容 |
|----------|------|
| `mujoco-rl-train-full` | 全 `ctrl` を PPO で学習（既定チェックポイント `ppo_full_actuators_live`） |
| `mujoco-rl-watch-full` | ライブ学習の Viewer（既定は `ppo_full_actuators_live` を監視） |
| `mujoco-rl-play-full` | 学習済み `ppo_full_actuators` を Viewer で再生 |

```bash
python -m mujoco_rl_sim.scripts.train_002_full_actuators --help
python -m mujoco_rl_sim.scripts.train_002_full_actuators --no-viewer
python -m mujoco_rl_sim.scripts.watch_full_actuators
python -m mujoco_rl_sim.scripts.play_full_actuators --model-base ppo_full_actuators
```

## HTTP API（要約）

すべて JSON。エラー時は HTTP 400 と `{"error": "..."}`（`/api/step` は 410 で廃止）。

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/health` | 生存確認 |
| GET | `/api/meta` | MJCF パス、アクチュエータ名、`timestep`、ステッパ状態、論理角メタ |
| GET | `/api/state` | 現在状態（`logical_deg` 等） |
| POST | `/api/reset` | リセット後に状態を返す |
| POST | `/api/set` | 単一サーボ（`robot-daemon` の `/set` 同形） |
| POST | `/api/set_multiple` | 複数サーボ一括 |
| PUT | `/api/ctrl` | ctrl 一括 |
| POST | `/api/pause` / `/api/resume` | 実時間ステッパの一時停止・再開 |

`mode` は `"rad"`（既定）・`"deg"`・`"logical"`。論理角は **`mujoco_realtime_sim/kinematics.py`** の `KINEMATICS` で MuJoCo 関節角に写像します。

## ディレクトリ構成（概要）

```
mujoco-sim/
  mujoco_sim_assets/
    paths.py           # 既定 MJCF パス・環境変数解決
    xmls/              # MJCF 世代別（既定は 001_leg_default/）
      001_leg_default/ # 胴固定（root freejoint なし）
      002_leg_freejoint/ # 001 と同構成 + root に freejoint
  mujoco_realtime_sim/
    __main__.py        # HTTP + オプション Viewer
    app.py             # Flask create_app()
    core.py            # Simulation（MjModel / MjData）
    realtime.py        # 実時間 mj_step スレッド
    passive_viewer.py
    kinematics.py
    viewer_cmd.py
  mujoco_rl_sim/
    envs/              # Gymnasium 環境（env_001_*.py の連番命名）
    scripts/           # 学習・ライブ Viewer・再生 CLI
  pyproject.toml
  requirements.txt
```

## 備考

- Gunicorn 等では **`mujoco_realtime_sim.app:create_app`** を指定。
- `robotics-hub`・`robot-daemon` とは **別プロセス**（ハブは HTTP のみ利用）。
