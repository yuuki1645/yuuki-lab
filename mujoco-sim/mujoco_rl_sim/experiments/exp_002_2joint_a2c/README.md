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
| `effort.py` | 関節トルク×角速度から筋負荷ペナルティを積算 |
| `termination.py` | 早期終了判定（basket / thigh / shank − floor 接触） |
| `episode_state.py` | エピソード内の `prev_x` / `prev_action` など |
| `agent.py` | Squashed Gaussian A2C |
| `train.py` | 学習ループ |
| `visualize.py` | チェックポイントを MuJoCo ビューアで実時間再生 |
| `preview_warmup.py` | `WARMUP_ACTION_FN` をビューアで実時間プレビュー（方策不要） |
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

## ウォームアップ行動のプレビュー

`config.py` の `WARMUP_ACTION_FN` / `WARMUP_DURATION_S` を、学習なしで MuJoCo ビューアに **50 Hz 実時間** で再生する。`warmup.py` を編集したあとの確認用。

```bash
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.preview_warmup

python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.preview_warmup --episodes 5 --print-every 10
```

| オプション | 説明 |
|-----------|------|
| `--episodes N` | N エピソードのウォームアップ区間だけ再生して終了（省略時 `0` = ビューアを閉じるまでループ） |
| `--print-every N` | N 制御ステップごとに行動・報酬を表示（省略時 `0` = 無効） |

- 各エピソードは `WARMUP_DURATION_S` 分だけ再生し、自動で `reset` する（方策フェーズには入らない）
- `WARMUP_ENABLED=False` でもプレビューは `WARMUP_ACTION_FN` を再生する（学習側のフラグとは独立）

## チェックポイントの可視化

MuJoCo パッシブビューアで **50 Hz（制御レート）の実時間** に再生する。

`mujoco-sim` ディレクトリで:

```bash
# 方策なし: 実験 XML（model/main.xml）のみ、ctrl 無操作
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.visualize

# チェックポイントで方策を再生
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.visualize \
  --checkpoint mujoco_rl_sim/experiments/exp_002_2joint_a2c/checkpoints/run_YYYYMMDD_HHMMSS/final.pt
```

チェックポイントは `checkpoints/run_YYYYMMDD_HHMMSS/` 以下に保存される。

| ファイル | 内容 |
|---------|------|
| `update_XXXXXX.pt` | 指定 update 時点の重み |
| `latest.pt` | 直近保存分 |
| `final.pt` | 学習終了時 |

### オプション

| オプション | 説明 |
|-----------|------|
| `--checkpoint` | 再生する `.pt`。省略時は `model/main.xml` のみ（方策・ctrl 無操作） |
| `--stochastic` | 確率的に行動（`--checkpoint` 指定時のみ。省略時は `act_eval`） |
| `--episodes N` | N エピソードで終了（省略時 `0` = ビューアを閉じるまで） |
| `--print-every N` | N 制御ステップごとに報酬などを表示（省略時 `0` = 無効） |
| `--device` | `torch.load` のデバイス（`--checkpoint` 指定時のみ。省略時 `cpu`） |

### 動作

- `--checkpoint` 省略時: `env.py` が `model/main.xml` を読み込み、`data.ctrl` を書き換えず物理のみ進める（reset 後の ctrl=0 を維持）
- `--checkpoint` 指定時: 保存済み方策で行動を決定
- エピソード終了（basket 接触 or `MAX_STEPS_PER_EPISODE` 到達）後は自動で `reset` し、再生を続ける
- ビューアウィンドウを閉じると終了
- 学習時と同じ `env.py` / 終了条件を使う

例:

```bash
# XML のみ（モデル確認用）
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.visualize

# final.pt を再生
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.visualize \
  --checkpoint checkpoints/run_20260520_160244/final.pt

# 3 エピソードだけ、50 ステップごとにログ
python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.visualize \
  --checkpoint checkpoints/run_20260520_160244/update_003000.pt \
  --episodes 3 \
  --print-every 50
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
reward = forward - effort_penalty
       (+ contact_floor_penalty if terminated)
```

- `forward` … 直立かつ（設定時）足接地のときだけ `max(0, dx) * SCALE + max(0, foot_dx) * SCALE`（imu_site と foot_site の合計）
- `effort_penalty` … `EFFORT_PENALTY_SCALE * Σ |τ·q̇|·dt / τ_max`（50 Hz ステップ内の物理ステップ合計）
- `contact_*_penalty` … basket / thigh_link / shank_link が床に触れた終了ステップのみ（法線力に比例、`config.py`）。リンクは basket の `CONTACT_LINK_PENALTY_SCALE` 倍（既定 0.5）

`dx` は制御ステップ（0.02 s）間の変位。係数は `config.py` を参照。

## 早期終了

| reason | 条件 | ペナルティ |
|--------|------|------------|
| `contact_basket` | basket geom が床に接触 | 法線力 [N] に比例（`CONTACT_FLOOR_*`、フルスケール） |
| `contact_thigh` | thigh_link geom が床に接触 | 同上 × `CONTACT_LINK_PENALTY_SCALE`（既定 0.5） |
| `contact_shank` | shank_link geom が床に接触 | 同上 × `CONTACT_LINK_PENALTY_SCALE`（既定 0.5） |
| `truncated` | `MAX_STEPS_PER_EPISODE` 到達（`train.py`） | なし |

IMU 高さ・直立度・後傾による早期終了は使わない。

## 関連ドキュメント

- [docs/control_timing_human_rl.md](../../../../docs/control_timing_human_rl.md)
- [docs/sim_human_comparison.md](../../../../docs/sim_human_comparison.md)
- [docs/human_joint_kinematics.md](../../../../docs/human_joint_kinematics.md)
