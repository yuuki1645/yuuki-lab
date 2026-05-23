# `programs/` — MuJoCo 試用スクリプト

`mujoco_test_*.py` は **本番パッケージ外**の小さな実験用スクリプトです。既定 MJCF はスクリプトごとに異なります（下表参照）。

## 実行のしかた

- **このディレクトリをカレントにして**実行するのが安全です（`001` / `002` / `008` / `010` は相対パス `../mujoco_sim_assets/...` を前提にしています）。

```bash
cd mujoco-sim/programs
python mujoco_test_001.py
```

- `004`〜`007` / `009` はスクリプト位置から `mujoco-sim` ルートを `sys.path` に載せるため、**`pip install -e .` なし**でも `mujoco_sim_common` を import できます。

## スクリプト一覧

| ファイル | 内容 | 既定 MJCF |
|----------|------|-----------|
| **`mujoco_test_001.py`** | 最小例。`mj_step` と passive viewer の `sync` のみ（IMU やネットワークなし）。 | `005_leg_1joint/main.xml` |
| **`mujoco_test_002.py`** | `001` に近いが、各ステップで IMU 加速度計を読み **g 換算**してコンソールに表示。ループは `time.sleep(0.5)` で遅め。 | `004_leg_1joint/main.xml` |
| **`mujoco_test_003.py`** | 別スレッドで Flask-SocketIO を立て、`rl_telemetry/step` で IMU 相当を emit する旧来パターンの例。**Hub 連携は `004` の `HubTelemetrySocketIoServer` 利用を推奨**。 | `004_leg_1joint/main.xml` |
| **`mujoco_test_004.py`** | `HubTelemetrySocketIoServer` で **8791** 上に Hub 用テレメトリを配信しつつ、同一シミュを passive viewer で表示。各 `mj_step` 後に `publish_step`（観測は g 換算の加速度 + ジャイロ）。 | `004_leg_1joint/main.xml` |
| **`mujoco_test_005.py`** | **オフスクリーン**で `mujoco.Renderer` により動画化し、Robotics Hub データビュワー用の **データセットフォルダ一式**（`video.mp4`, `imu.csv`, `servo.csv`, `manifest.json`）を **カレント直下の `--dataset` 名**に出力。詳細は `python mujoco_test_005.py --help` とリポジトリ直下 `mujoco-sim/README.md` の「オフスクリーン動画化」節を参照。 | `004_leg_1joint/main.xml`（`--xml` で変更可） |
| **`mujoco_test_006.py`** | **Gymnasium + Stable-Baselines3（PPO）** で単純な強化学習。報酬はルートの **世界座標 +X 方向の並進速度**を主にし、転倒（ベース高さ低下）で終了。`pip install -e ".[rl]"` が必要。`python mujoco_test_006.py --help`。 | `004_leg_1joint/main.xml`（`--xml` で変更可） |
| **`mujoco_test_007.py`** | **006 で保存した PPO の .zip** を読み込み、**passive viewer** で方策を再生。`python mujoco_test_007.py --model ppo_006.zip`。006 と同じ RL 依存。 | `004_leg_1joint/main.xml`（`--xml` で変更可） |
| **`mujoco_test_008.py`** | `launch`（ブロッキング）で `005` モデルを表示するだけの最小 viewer。 | `005_leg_1joint/main.xml` |
| **`mujoco_test_009.py`** | passive viewer + **ビュワー補助 HTTP**（既定 **8788**）。Hub「MuJoCo ビュワー補助」と接続。`--no-http` で viewer のみ。 | `004_leg_1joint/main.xml`（`--xml` で変更可） |
| **`mujoco_test_010.py`** | 2 関節モデル（`007_leg_2joint`）で site・関節・COM などをコンソールに表示するデバッグ用 passive viewer。 | `007_leg_2joint/main.xml` |

## 依存のメモ

- **001〜004 / 008 / 010**: プロジェクトの `pip install -e .`（MuJoCo / Flask 等）。`004` の Socket.IO は `mujoco_sim_common.telemetry`。
- **005**: 追加で **`pip install -e ".[video]"`**（`imageio` + `imageio-ffmpeg`）。
- **006 / 007**: 追加で **`pip install -e ".[rl]"`**（`gymnasium` + `stable-baselines3`）。
- **009**: `pip install -e .`（`mujoco_sim_common.viewer_aux_bridge`）。

## 関連ドキュメント

- パッケージ全体: `../README.md`（`mujoco-sim` ルート）
- 2 関節 A2C 実験: `../mujoco_rl_sim/experiments/exp_002_2joint_a2c/README.md` など
- データビュワーへの配置: `robotics-hub/README.md` のデータセット節
