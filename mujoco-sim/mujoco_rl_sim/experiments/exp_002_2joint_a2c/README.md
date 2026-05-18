# exp_002: 2 関節脚 A2C

`exp_001_2joint_a2c` をコピーした実験です。**制御レートのみ exp_001 と異なります**（後述）。
モデル・チェックポイント・ユーティリティはこのフォルダ内に閉じています（`mujoco_rl_sim/lib` 非依存）。

## 制御レート（exp_001 との差分）

| 項目 | exp_001 | exp_002 |
|------|---------|---------|
| 物理 (`mj_step`) | 500 Hz（`timestep=0.002`） | 同左 |
| ポリシー（`env.step`） | 500 Hz（1 step = 1 `mj_step`） | **50 Hz**（1 step = 10 `mj_step`） |
| `MAX_DX_PER_STEP` | 0.05 m | **0.5 m**（制御ステップ幅に合わせて ×10） |
| `GAMMA` | 0.99 | **≈ 0.904**（`0.99^10`、実時間の割引を合わせる） |
| `MAX_STEPS_PER_EPISODE` | 3000（約 6 s） | **300**（約 6 s） |

設計メモ: [docs/control_timing_human_rl.md](../../../../docs/control_timing_human_rl.md)

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `config.py` | 報酬・観測スケール・A2C・学習ループ・`FRAME_SKIP` の定数 |
| `env.py` | MuJoCo 環境（`reset` / `step`、各コンポーネントの配線） |
| `observation.py` | `ObsExp002` の組み立て（`Observation.build`） |
| `reward.py` | 報酬項の計算（終了判定は含まない） |
| `termination.py` | 転倒などの終了判定 |
| `episode_state.py` | エピソード内の `prev_x` / `prev_action` など |
| `agent.py` | Squashed Gaussian A2C |
| `train.py` | 学習ループ |
| `debug.py` | ターミナル向けステップ表示 |
| `model/main.xml` | 実験専用 MuJoCo モデル |
| `lib/` | 行動マッピング・観測正規化・デバッグ表示（実験内コピー） |
| `checkpoints/` | 学習時に自動作成されるチェックポイント |

外部依存: MuJoCo / PyTorch / `mujoco_sim_common`（ビューア表示のみ）。

## 実行方法

`mujoco-sim` ディレクトリで:

```bash
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.train
```

## モデル

- XML: `model/main.xml`（このフォルダ内。元は `mujoco_sim_assets/xmls/007_leg_2joint/main.xml`）
- 行動: 膝・足首の目標角（`[-1,1]` → 各 actuator の `ctrlrange`）
- 前進方向: `imu_site` のワールド **+X**

## 符号约定

| 関節 | `qpos` / `ctrl` の + 方向 |
|------|---------------------------|
| 膝（+Y ヒンジ） | 後方屈曲（人間と同じ） |
| 足首（+Y ヒンジ） | 底屈（地面を蹴る） |

## 観測（20 次元、おおよそ [-1, 1]）

| # | 名前 | 内容 | 正規化 |
|---|------|------|--------|
| 0 | rel_imu_x | エピソード開始からの IMU X [m] | ÷ 2.0 |
| 1 | dx | **50 Hz ステップ間**の IMU X 変位 [m] | ÷ 0.5 |
| 2 | foot_on_floor | 足裏−床接触 | -1 / +1 |
| 3–5 | imu_gyro | 角速度 [rad/s] | ÷ 10 |
| 6–8 | imu_zaxis | 姿勢（単位ベクトル） | そのまま |
| 9 | imu_z | IMU 高さ [m] | 0〜1.2 m → [-1,1] |
| 10 | foot_z | 足先高さ [m] | 同上 |
| 11 | foot_xaxis_z | `framexaxis` の z 成分 | そのまま |
| 12 | knee | 膝 qpos [rad] | `jnt_range` → [-1,1] |
| 13 | ankle | 足首 qpos [rad] | 同上 |
| 14–15 | knee/ankle vel | 角速度 [rad/s] | ÷ 10 |
| 16 | com_x | COM X − 趾 [m] | ÷ 0.6 |
| 17 | com_z | COM 高さ [m] | 0〜1.2 m → [-1,1] |
| 18–19 | prev_action | 直前指令 | [-1, 1] |

## 報酬

```
reward = dx * FORWARD_REWARD_SCALE
       + upright * UPRIGHT_BONUS_SCALE
       + knee_human_flex_bonus
       - knee_wrong_penalty
       (+ FALL_PENALTY if terminated)
```

`dx` は制御ステップ（0.02 s）間の変位。係数は `config.py` を参照。

## 関連ドキュメント

- [docs/control_timing_human_rl.md](../../../../docs/control_timing_human_rl.md)
- [docs/sim_human_comparison.md](../../../../docs/sim_human_comparison.md)
- [docs/human_joint_kinematics.md](../../../../docs/human_joint_kinematics.md)
