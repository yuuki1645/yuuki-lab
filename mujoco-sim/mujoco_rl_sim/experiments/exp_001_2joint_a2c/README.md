# exp_001: 2 関節脚 A2C

旧 `010` 系（`env_010_a2c` / `agent_010_a2c`）をこのフォルダに集約した実験です。

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `config.py` | 報酬・観測スケール・A2C・学習ループの定数 |
| `env.py` | MuJoCo 環境（`reset` / `step`、各コンポーネントの配線） |
| `observation.py` | `ObsExp001` の組み立て（`Observation.build`） |
| `reward.py` | 報酬項の計算（終了判定は含まない） |
| `termination.py` | 転倒などの終了判定 |
| `episode_state.py` | エピソード内の `prev_x` / `prev_action` など |
| `agent.py` | Squashed Gaussian A2C |
| `train.py` | 学習ループ |
| `debug.py` | ターミナル向けステップ表示 |
| `model/main.xml` | 実験専用 MuJoCo モデル（`mujoco_sim_assets` 非依存） |

共通処理は `mujoco_rl_sim/lib/` を参照。

## 実行方法

`mujoco-sim` ディレクトリで:

```bash
python -m mujoco_rl_sim.experiments.exp_001_2joint_a2c.train
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
| 1 | dx | 1 ステップの IMU X 変位 [m] | ÷ 0.05 |
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

係数は `config.py` を参照。

## 関連ドキュメント

- [docs/sim_human_comparison.md](../../../../docs/sim_human_comparison.md)
- [docs/human_joint_kinematics.md](../../../../docs/human_joint_kinematics.md)
