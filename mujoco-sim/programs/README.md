# `programs/` — MuJoCo 試用スクリプト

`mujoco_test_*.py` は **本番パッケージ外**の小さな実験用スクリプトです。多くは `mujoco_sim_assets/xmls/004_leg_1joint/main.xml` を既定モデルにしています。

## 実行のしかた

- **このディレクトリをカレントにして**実行するのが安全です（`001` / `002` は相対パス `../mujoco_sim_assets/...` を前提にしています）。

```bash
cd mujoco-sim/programs
python mujoco_test_001.py
```

- `004` / `005` はスクリプト位置から `mujoco-sim` ルートを `sys.path` に載せるため、**`pip install -e .` なし**でも `mujoco_sim_common` を import できます。

## スクリプト一覧

| ファイル | 内容 |
|----------|------|
| **`mujoco_test_001.py`** | 最小例。`mj_step` と passive viewer の `sync` のみ（IMU やネットワークなし）。 |
| **`mujoco_test_002.py`** | `001` に近いが、各ステップで IMU 加速度計を読み **g 換算**してコンソールに表示。ループは `time.sleep(0.5)` で遅め。 |
| **`mujoco_test_003.py`** | 別スレッドで Flask-SocketIO を立て、`rl_telemetry/step` で IMU 相当を emit する旧来パターンの例。**Hub 連携は `004` の `HubTelemetrySocketIoServer` 利用を推奨**。 |
| **`mujoco_test_004.py`** | `HubTelemetrySocketIoServer` で **8791** 上に Hub 用テレメトリを配信しつつ、同一シミュを passive viewer で表示。各 `mj_step` 後に `publish_step`（観測は g 換算の加速度 + ジャイロ）。 |
| **`mujoco_test_005.py`** | **オフスクリーン**で `mujoco.Renderer` により動画化し、Robotics Hub データビュワー用の **データセットフォルダ一式**（`video.mp4`, `imu.csv`, `servo.csv`, `manifest.json`）を **カレント直下の `--dataset` 名**に出力。詳細は `python mujoco_test_005.py --help` とリポジトリ直下 `mujoco-sim/README.md` の「オフスクリーン動画化」節を参照。 |
| **`mujoco_test_006.py`** | **Gymnasium + Stable-Baselines3（PPO）** で単純な強化学習。報酬はルートの **世界座標 +X 方向の並進速度**を主にし、転倒（ベース高さ低下）で終了。`pip install -e ".[rl]"` が必要。`python mujoco_test_006.py --help`。 |

## 依存のメモ

- **001〜004**: プロジェクトの `pip install -e .`（MuJoCo / Flask 等）。`004` の Socket.IO は `mujoco_sim_common.telemetry`。
- **005**: 追加で **`pip install -e ".[video]"`**（`imageio` + `imageio-ffmpeg`）。
- **006**: 追加で **`pip install -e ".[rl]"`**（`gymnasium` + `stable-baselines3`）。

## 関連ドキュメント

- パッケージ全体: `../README.md`（`mujoco-sim` ルート）
- データビュワーへの配置: `robotics-hub/README.md` のデータセット節
