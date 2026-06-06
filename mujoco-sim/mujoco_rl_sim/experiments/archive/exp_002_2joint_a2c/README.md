# exp_002: 2 関節脚 A2C

`exp_001_2joint_a2c` をコピーした実験です。**制御レートのみ exp_001 と異なります**（後述）。
モデル・チェックポイント・ユーティリティはこのフォルダ内に閉じています（`実験内 lib/` 非依存）。

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
| `train.py` | 学習ループ（CLI: 再開・LR・update 数） |
| `checkpoint.py` | チェックポイント保存・読み込み |
| `wandb_logging.py` | 任意 Weights & Biases ロギング |
| `warmup.py` | エピソード開始時の固定ウォームアップ行動 |
| `visualize.py` | チェックポイントを MuJoCo ビューアで実時間再生 |
| `preview_warmup.py` | `WARMUP_ACTION_FN` をビューアで実時間プレビュー（方策不要） |
| `debug.py` | ターミナル向けステップ表示 |
| `model/main.xml` | 実験専用 MuJoCo モデル |
| `lib/` | 行動マッピング・観測正規化・デバッグ表示（実験内コピー） |
| `checkpoints/` | 学習時に自動作成されるチェックポイント |

外部依存: MuJoCo / PyTorch / `mujoco_sim_common`（ビューア表示のみ）。

## 学習（train）

`mujoco-sim` ディレクトリで実行する。ハイパーパラメータの本体は `config.py`（`NUM_UPDATES`, `LR`, 報酬係数など）。

### ゼロから学習

```bash
python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.train
```

- 1 回の実行ごとに `checkpoints/run_YYYYMMDD_HHMMSS/` が新規作成される
- `CHECKPOINT_EVERY`（既定 1000）ごとに `update_XXXXXX.pt` を保存
- 終了時に `final.pt`（`CHECKPOINT_SAVE_FINAL=True` のとき）

### チェックポイントから再開（微調整）

**新しい checkpoint ディレクトリ**と**新しい wandb run**を作る。update 番号・`total_env_steps`・`episodes_finished` は ckpt から継続する。

```bash
python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.train \
  --resume checkpoints/run_20260520_160244/update_005000.pt \
  --lr 1e-4 \
  --num-updates 1500
```

上記の例: ckpt が `update=5000` なら、**5001 から 6500 まで** 1500 回更新し、新 run に `update_006500.pt` などが保存される。

| オプション | 説明 |
|-----------|------|
| `--resume PATH` | 再開元 `.pt`。相対パスは **この実験フォルダ（exp_002）基準** |
| `--lr FLOAT` | 学習率（`config.LR` の上書き）。指定時は **optimizer state は読み込まない**（新しい Adam） |
| `--num-updates N` | **この run だけ**行う方策更新回数（省略時は `config.NUM_UPDATES`） |
| `--load-optimizer` | `--resume` 時に optimizer も復元（`--lr` 指定時は無効） |
| `--wandb-run-name NAME` | wandb run 名（省略時、再開時は `resume_u005000_lr1e-4` など自動） |

**再開時の既定**: 重みのみ復元 + 新しい optimizer（`config.LR`）。以前の Adam の momentum を引き継ぐ場合は `--load-optimizer`（`--lr` なし）。

**学習率（LR）**: `config.LR`（既定 `3e-4`）。Actor / Critic 共通の Adam 学習率。微調整では `1e-4` などに下げることが多い。

**速度**: `config.ENABLE_VIEWER = False` にすると MuJoCo ビューアを使わず学習が速くなる（本番学習向け）。

### wandb

- `config.USE_WANDB = True` で有効（`pip install wandb`）
- 無効化: `set WANDB_MODE=disabled`（Windows）または環境変数 `WANDB_MODE=disabled`
- プロジェクト名: `config.WANDB_PROJECT`（`exp_002_2joint_a2c`）
- 再開 run にはタグ `finetune`, `resume` と config に `resume_checkpoint`, `resume_base_update`, `end_update_target` などを記録
- エピソード指標: `episode/return`, `episode/length`, `episode/forward_*`, `termination/rolling_rate_*` など

### ウォームアップ（学習時）

各エピソードの先頭 `WARMUP_DURATION_S`（既定 1.2 s ≒ 50 制御ステップ @ 50 Hz）は `WARMUP_ACTION_FN` の固定行動。方策の `store` には入れない（方針 B）。`config.WARMUP_ENABLED` で on/off。

### 推奨ワークフロー（長時間学習後）

1. wandb で `episode/return`・`episode/length`・`termination/rolling_rate_*` を確認し、ピーク付近の `update_XXXXXX.pt` を選ぶ  
2. `visualize --checkpoint ... --stochastic` で挙動を確認（学習時は確率行動のため）  
3. 微調整する場合は `--resume` + `--lr` + 短い `--num-updates` で **新 run** を開始  
4. 悪化したらその run を止め、直前の良い ckpt に戻す（`final.pt` 一択にしない）

### 主な `config.py` 定数（学習）

| 定数 | 既定（目安） | 意味 |
|------|-------------|------|
| `NUM_UPDATES` | 10100 | 1 run の方策更新回数（`--num-updates` で CLI 上書き可） |
| `ROLLOUT_STEPS` | 512 | 1 update あたりの on-policy ステップ数 |
| `LR` | 3e-4 | Adam 学習率（`--lr` で上書き可） |
| `ENTROPY_COEF` | 0.04 | 探索（エントロピー bonus） |
| `FORWARD_REWARD_SCALE` | 80 | 前進報酬スケール |
| `FORWARD_MIN_UPRIGHT` | 0.72 | 前進報酬を出す最低直立度 |
| `CHECKPOINT_EVERY` | 1000 | 何 update ごとに numbered ckpt を保存するか |

## ウォームアップ行動のプレビュー

`config.py` の `WARMUP_ACTION_FN` / `WARMUP_DURATION_S` を、学習なしで MuJoCo ビューアに **50 Hz 実時間** で再生する。`warmup.py` を編集したあとの確認用。

```bash
python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.preview_warmup

python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.preview_warmup --episodes 5 --print-every 10
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
python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.visualize

# チェックポイントで方策を再生（相対パスは exp_002 フォルダ基準）
python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.visualize \
  --checkpoint checkpoints/run_YYYYMMDD_HHMMSS/final.pt
```

チェックポイントは **`experiments/archive/exp_002_2joint_a2c/checkpoints/run_YYYYMMDD_HHMMSS/`** 以下に保存される（**train のたびに新しい `run_*` ディレクトリ**）。`--resume` / `--checkpoint` の相対パスは **この実験フォルダ基準**（例: `checkpoints/run_.../final.pt`）。絶対パスも可。

| ファイル | 内容 |
|---------|------|
| `update_XXXXXX.pt` | その update 時点の actor / critic / optimizer とメタデータ |
| `latest.pt` | 直近の定期保存（`CHECKPOINT_SAVE_LATEST`） |
| `final.pt` | その run の学習終了時 |

`.pt` の主なフィールド: `update`, `total_env_steps`, `episodes_finished`, `obs_dim`, `action_dim`, `actor`, `critic`, `optimizer`。

**可視化の目安**: 長時間学習では `final.pt` より **`update_XXXXXX.pt` のピーク付近**（例: 5000）を `--stochastic` で確認するとよい。崩壊後の `final` は性能が落ちていることがある。

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
python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.visualize

# ピーク付近の ckpt（学習時の挙動確認: --stochastic 推奨）
python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.visualize \
  --checkpoint checkpoints/run_20260520_160244/update_005000.pt \
  --stochastic

# 3 エピソードだけ、50 ステップごとにログ
python -m mujoco_rl_sim.experiments.archive.exp_002_2joint_a2c.visualize \
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

## 観測（19 次元、おおよそ [-1, 1]）

固定スポーンでは累積 `rel_imu_x` が世界 X の進行距離に近く、`dx` と冗長なため **ポリシー入力からは除外**（デバッグ表示用に `StepPhysics.rel_imu_x` は残す）。

| # | 名前 | 内容 | 正規化 |
|---|------|------|--------|
| 0 | dx | **50 Hz ステップ間**の IMU X 変位 [m] | ÷ 0.5 |
| 1 | foot_on_floor | 足裏−床接触 | -1 / +1 |
| 2–4 | imu_gyro | 角速度 [rad/s] | ÷ 10 |
| 5–7 | imu_zaxis | 姿勢（単位ベクトル） | そのまま |
| 8 | imu_z | IMU 高さ [m] | 0〜1.2 m → [-1,1] |
| 9 | foot_z | 足先高さ [m] | 同上 |
| 10 | foot_xaxis_z | `framexaxis` の z 成分 | そのまま |
| 11 | knee | 膝 qpos [rad] | `jnt_range` → [-1,1] |
| 12 | ankle | 足首 qpos [rad] | 同上 |
| 13–14 | knee/ankle vel | 角速度 [rad/s] | ÷ 10 |
| 15 | com_x | COM X − 趾 [m] | ÷ 0.6 |
| 16 | com_z | COM 高さ [m] | 0〜1.2 m → [-1,1] |
| 17–18 | prev_action | 直前指令 | [-1, 1] |

**注意**: `obs_dim=20` の旧チェックポイントはそのまま読み込めない。再学習または `obs_dim=19` で新規学習する。

## 報酬

```
reward = forward - effort_penalty
       (+ contact_floor_penalty if terminated)
```

- `forward` … 直立かつ（設定時）足接地のときだけ `max(0, dx) * SCALE + max(0, foot_dx) * SCALE`（imu_site と foot_site の合計）
- `effort_penalty` … `EFFORT_PENALTY_SCALE * Σ |τ·q̇|·dt / τ_max`（50 Hz ステップ内の物理ステップ合計）。**既定は `APPLY_EFFORT_PENALTY = False` のため報酬には入らず計測のみ**（`config.py` で有効化可）
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
