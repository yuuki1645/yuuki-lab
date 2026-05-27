# Cursor / AI エージェント向け — exp_019

## 位置づけ

- **学習・報酬・観測は exp_018 と同一**（fork コピー）
- **テレメトリ**: `mujoco_rl_sim/telemetry/biped_ppo.py`（スキーマ `biped_ppo_v1`）
- **robotics-hub** `/telemetry` の学習ストリームは本実験向けに更新済み

## 既定動作

| 設定 | 値 |
|------|-----|
| `ENABLE_VIEWER` | `True` |
| `STEP_WALL_SLEEP_SEC` | `CONTROL_TIMESTEP_S`（50 Hz） |
| `TELEMETRY_ENABLED` | `True` / ポート 8791 |

## 変更時の注意

- 観測次元・`PolicyObs` レイアウトを変えたら **`biped_ppo.py` の `_obs_slices` と Hub の型・UI** を同時に更新する
- 実機 IMU（`robot-daemon`）のコードパスは **触らない**（Hub テレメトリページの daemon 部分のみ RL 側を修正）
