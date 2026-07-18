# BipedPpoWalk — Isaac Lab タスク詳細解説

**Yuuki Lab 両脚交互片脚歩行 PPO** タスクの解説です（**リポジトリ強化学習本線**の Direct 実装）。  
[Isaac Lab DirectRLEnv](https://isaac-sim.github.io/IsaacLab/) 上で学習します。由来は MuJoCo [exp_030_biped_ppo_walk](../../../../../../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/)（参照・レガシー）。

## 目次

1. [タスク概要](#タスク概要)
2. [登録タスク ID](#登録タスク-id)
3. [ディレクトリ構成](#ディレクトリ構成)
4. [ロボットとシミュレーション](#ロボットとシミュレーション)
5. [行動空間（12 次元）](#行動空間12-次元)
6. [観測空間（54 次元）](#観測空間54-次元)
7. [報酬設計](#報酬設計)
8. [終了条件](#終了条件)
9. [PPO 学習設定](#ppo-学習設定)
10. [学習用 vs 再生用の設定差分](#学習用-vs-再生用の設定差分)
11. [実行方法](#実行方法)
12. [ログ・評価指標](#ログ評価指標)
13. [exp_030（MuJoCo）との対応表](#exp_030mujocoとの対応表)
14. [変更時のガイド](#変更時のガイド)

---

## タスク概要

| 項目 | 内容 |
|------|------|
| タスク種別 | Isaac Lab **DirectRLEnv**（Manager-Based ではない） |
| 目標 | 世界座標 **+X 方向** への交互片脚歩行 |
| 関節数 | 12 DOF（左右脚 5 + 胴体 2） |
| 制御方式 | ポジション目標（ImplicitActuator / PD） |
| 学習アルゴリズム | PPO（[RSL-RL](https://github.com/leggedrobotics/rsl_rl)） |
| 並列環境 | 学習時デフォルト **4096**（RTX 4080 SUPER 16GB 想定） |

歩行の定義（exp_030 と共通）:

- **片足支持**（左右どちらか 1 本だけ接地）のときのみ主な前進報酬を付与
- **両足接地**中の前進はペナルティで抑制（すり足・前転ハック防止）
- **両足非接地**が長いと飛翔ペナルティ（ホップ抑制）
- **交互着地**・支持脚の push-off / landing・遊脚の swing clearance を shaping で誘導

---

## 登録タスク ID

`__init__.py` で Gymnasium に登録されます（接頭辞 `YuukiLab-`）。

| Task ID | 設定クラス | 用途 |
|---------|-----------|------|
| `YuukiLab-BipedPpoWalk-Direct-v0` | `BipedPpoWalkEnvCfg` | 学習（4096 env・fabric clone） |
| `YuukiLab-BipedPpoWalk-Direct-Play-v0` | `BipedPpoWalkEnvCfg_PLAY` | 再生・録画（16 env・通常 clone） |

```bash
python scripts/list_envs.py --headless
```

---

## ディレクトリ構成

```
biped_ppo_walk/
├── README.md                 # 本ドキュメント
├── __init__.py               # Gym 登録
├── biped_ppo_walk_env.py     # DirectRLEnv 本体（観測・報酬・リセット）
├── biped_ppo_walk_env_cfg.py # 環境・報酬・終了の設定（@configclass）
├── agents/
│   └── rsl_rl_ppo_cfg.py     # PPO ハイパーパラメータ
└── mdp/                      # MDP 部品（exp_030 sim/* + lib/* の torch 版）
    ├── actuators.py          # 関節名・ctrlrange・site オフセット
    ├── action.py             # [-1,1] → 関節位置目標
    ├── obs_norm.py           # 観測正規化
    ├── pose.py               # 姿勢量（lean, heading, tilt）
    ├── episode_state.py      # 歩行位相（着地エッジ・交互歩行）
    ├── reward.py             # ステップ報酬
    └── termination.py        # 姿勢終了・接地判定
```

ロボットアセットは別パッケージにあります:

- `yuuki_isaac_lab/assets/robots/yuuki_biped/` — MJCF（`main_isaac.xml`）と `YUUKI_BIPED_CFG`

---

## ロボットとシミュレーション

### 関節（12 DOF）

`mdp/actuators.py` の `JOINT_NAMES` 順（行動・観測の並びと一致）:

| # | 関節名 | 役割 |
|---|--------|------|
| 0–4 | `left_hip_roll` … `left_ankle_roll` | 左脚 |
| 5–9 | `right_hip_roll` … `right_ankle_roll` | 右脚 |
| 10–11 | `basket_top_roll`, `balance_pitch` | 胴体バランス |

### 制御周期

| パラメータ | 値 | 意味 |
|-----------|-----|------|
| `sim.dt` | 0.002 s | 物理ステップ **500 Hz** |
| `decimation` | 10 | ポリシーは 10 物理ステップに 1 回 |
| 制御周波数 | **50 Hz** | RL の 1 step = 0.02 s |
| `episode_length_s` | 30.0 s | 最大 **1500** 制御ステップ / エピソード |

### シーン

- 地面: `GroundPlaneCfg`（摩擦 1.15、反発 0）
- 初期姿勢: 立位 keyframe（全関節 0 rad、ルート高さ 0.66 m）
- リセット時: `reset_joint_noise_rad`（既定 0.025 rad）で関節角に微小ノイズ

### 接地判定

MuJoCo の geom 接触の代わりに、足裏・踵・つま先 site の **高さヒステリシス** を使用（PhysX 向け）:

- `FOOT_CONTACT_Z_ON = 0.018 m` — min Z がこれ以下で接地候補
- `FOOT_CONTACT_Z_OFF = 0.045 m` — max Z がこれ以上なら離地確定

---

## 行動空間（12 次元）

ポリシー出力は **[-1, 1]**（`mdp/action.py`）。

```
action = 0  →  中立姿勢（stand keyframe、全関節 0 rad）
action > 0  →  neutral から ctrlrange 上限方向
action < 0  →  neutral から ctrlrange 下限方向
```

非対称な `ctrlrange`（膝は 0〜1.745 rad など）にも対応した写像です。  
適用は `ImplicitActuatorCfg` による関節位置目標（MuJoCo position actuator 相当）です。

---

## 観測空間（54 次元）

MuJoCo exp_030 の **51 次元** に、歩行位相を表す **3 次元** を追加した構成です。

### 次元一覧

| idx | 次元数 | 内容 | 正規化 |
|-----|--------|------|--------|
| 0 | 1 | IMU +X 変位 `dx` [m/step] | `clip_scale(·, max_dx_per_step)` |
| 1–3 | 3 | 角速度 `imu_gyro` [rad/s] | `max_gyro_rad_s = 10` |
| 4–6 | 3 | IMU 上向き軸 `imu_zaxis` | なし（単位ベクトル） |
| 7 | 1 | IMU 高さ `imu_z` [m] | `height_to_norm(0, 1.2)` |
| 8–9 | 2 | 左右足接地 | +1 / -1 |
| 10–11 | 2 | 左右足 +X 変位 | `max_foot_dx_per_step` |
| 12–13 | 2 | 左右足高さ | `height_to_norm(0, 0.35)` |
| 14 | 1 | 片足支持フラグ | +1 / -1 |
| 15–26 | 12 | 関節角 | `range_to_norm(ctrlrange)` |
| 27–38 | 12 | 関節角速度 | `max_joint_vel_rad_s = 10` |
| 39–50 | 12 | 前ステップ action | そのまま [-1, 1] |
| **51** | **1** | **片脚支持側** | +1=左, -1=右, 0=非片脚 |
| **52** | **1** | **same_side_streak / 40** | 同側片脚の連続ステップ（clamp 1） |
| **53** | **1** | **episode_progress** | `step / max_episode_length` |

`max_dx_per_step` / `max_foot_dx_per_step` は `decimation` を掛けた値（`get_max_dx_per_step`）です。

### exp_030 との差分

| 項目 | exp_030 (MuJoCo) | Isaac Lab |
|------|------------------|-----------|
| 観測次元 | 51 | **54**（位相 3 次元追加） |
| 接地判定 | geom 接触 | site 高さヒステリシス |
| 契約検証 | `contract/biped_walk_v1.py` | なし（Isaac 専用ポリシー） |

**MuJoCo で学習した ckpt はそのまま読み込めません**（観測次元が異なるため）。

---

## 報酬設計

設定の正本: `biped_ppo_walk_env_cfg.py` の `BipedRewardCfg`  
実装の正本: `mdp/reward.py` の `compute_step_reward`

MuJoCo 側の詳細解説: [docs/experiments/exp_030_biped_ppo_walk/reward.md](../../../../../../../docs/experiments/exp_030_biped_ppo_walk/reward.md)

### 合成式（1 制御ステップ）

```
reward_total = forward + shaping - effort_penalty
```

- `forward` = `forward_imu` + `forward_foot` + `forward_vel`（`enable_forward_vel` は既定 **False**）
- `shaping` = ボーナス群 − ペナルティ群（下表参照）
- `effort_penalty` = `|τ·q̇|` の簡易積分 × `effort_penalty_scale`

姿勢終了ペナルティ（`-30`）は `biped_ppo_walk_env.py` の `_get_rewards` で、**エピソード終了時のみ**加算されます（毎ステップ付与すると学習が破壊されるため）。

### 前進報酬のゲート（`forward_allowed`）

次をすべて満たすときのみ `forward_imu` / `forward_foot` が有効:

1. `upright >= forward_min_upright`（0.55）
2. いずれかの足が接地（`forward_require_foot_contact`）
3. **片足支持**（`forward_require_single_support`）
4. 両足支持かつ前傾が大きいときは遮断（`forward_block_lean_both_feet`）
5. 同側片脚が長く続く degenerate gait では遮断（`forward_block_same_side_streak`）

### 主な報酬項

| カテゴリ | 設定フラグ | 概要 |
|---------|-----------|------|
| 前進 IMU | `enable_forward` | 片脚支持時の IMU +X 増分 × 35 |
| 前進 足 | `enable_forward_foot` | 支持脚の +X 増分 × 35 |
| 進捗 | `enable_progress` | エピソード内 IMU 最高更新量 × 35 |
| 直立ボーナス | `enable_upright_bonus` | 前傾しすぎない直立姿勢 |
| push-off | `enable_walk_shaping` | 支持脚の蹴り出し |
| landing | 同上 | 着地品質（つま先・踵の高さ、前傾） |
| 交互着地 | 同上 | 反対脚支持後の着地 |
| 右足着地 / 右片脚 | 同上 | 左右バランスの degenerate gait 対策 |
| foot swap | 同上 | 左↔右片脚支持の切り替え |
| swing clearance | 同上 | 遊脚の最低高度 |
| 生存ボーナス | `enable_alive_bonus` | 直立維持の小さな報酬 |
| 持続ボーナス | `enable_duration_bonus` | エピソード後半ほど増幅 |
| 移動マイルストーン | `enable_displacement_milestones` | 1/2/5/10/15 m 到達ボーナス |
| 生存マイルストーン | `enable_survival_milestones` | 80/150/300/600/1200 step 到達ボーナス |
| 両足支持ペナルティ | `enable_double_support` | すり足・前転抑制 |
| 飛翔ペナルティ | `enable_flight_duration` | 4 step 超の両足非接地 |
| 姿勢ペナルティ | `enable_posture_penalties` | 後傾・前傾・横倒れ・高さ・膝過屈曲 |
| エフォート | `enable_effort` | トルク×角速度ペナルティ |
| 行動変化率 | — | `action_rate_penalty_scale` |
| 横速度・角速度 | — | ドリフト・ふらつき抑制 |

`shaping_require_forward_motion=True` のとき、shaping 系は最小前進量 `shaping_min_dx` を満たす場合のみ付与されます（静止立位での報酬ハック抑制）。

---

## 終了条件

設定: `BipedTerminationCfg` / 実装: `mdp/termination.py` + `biped_ppo_walk_env.py`

MuJoCo 側: [docs/experiments/exp_030_biped_ppo_walk/termination.md](../../../../../../../docs/experiments/exp_030_biped_ppo_walk/termination.md)

### 姿勢による早期終了（ヒステリシス付き）

以下のいずれかが **連続 `bad_pose_consecutive_steps`（12）ステップ** 続くと `terminated=True`:

| 条件 | 閾値 |
|------|------|
| IMU 高さが低すぎ | `imu_z < 0.25 m` |
| 直立度が低すぎ | `upright < 0.46` |
| 後傾が大きすぎ | `lean_fwd_body < -0.40` |
| 両足支持のまま前傾 | `lean_fwd_body > 0.22` |

終了時に `pose_termination_penalty = -30` を 1 回付与。

### タイムアウト

`episode_length_s = 30.0` → 1500 制御ステップで `truncated=True`（時間切れ）。

---

## PPO 学習設定

正本: `agents/rsl_rl_ppo_cfg.py`（exp_030 `conf/ppo/default.yaml` 由来）

| 項目 | 値 |
|------|-----|
| `num_steps_per_env` | 24 |
| `max_iterations` | 5000 |
| `save_interval` | 10 |
| `experiment_name` | `biped_ppo_walk` |
| ロガー | WandB（`wandb_project=biped_ppo_walk`） |
| ネットワーク | Actor/Critic MLP [256, 256, 128], ELU |
| `learning_rate` | 1e-4（adaptive） |
| `gamma` | 0.904（= 0.99^10、物理 10 step 相当） |
| `lam` | 0.95 |
| `entropy_coef` | 0.008 |
| 観測正規化 | Actor/Critic とも有効 |

チェックポイント保存先: `isaac-lab/logs/rsl_rl/biped_ppo_walk/<timestamp>/`

---

## 学習用 vs 再生用の設定差分

| 項目 | `BipedPpoWalkEnvCfg`（学習） | `BipedPpoWalkEnvCfg_PLAY`（再生） |
|------|------------------------------|-----------------------------------|
| `num_envs` | 4096 | 16 |
| `replicate_physics` | True | False |
| `clone_in_fabric` | True | False |
| `viewer` | デフォルト | 4×4 配置が見えるカメラ |

`replicate_physics + fabric` は学習スループット向けですが、GUI では env_0 以外が site だけ見えることがあるため、play では通常 clone を使います。

---

## 実行方法

`isaac-lab/` ディレクトリで実行（`env_isaaclab` 等を activate 済みであること）。

```powershell
# セットアップ（初回）
python -m pip install -e source/yuuki_isaac_lab

# タスク確認
python scripts/list_envs.py --headless

# スモーク学習
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 64 --max_iterations 5

# 本番学習
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 4096

# 定量評価
python scripts/eval_biped_walk.py --load_run <run_dir_name>

# 可視化再生
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-Direct-Play-v0 --load_run <run_dir_name>
```

PowerShell で複数行に分けるときは行末に **バッククォート `` ` ``** を使います（`\` は不可）。

---

## ログ・評価指標

### TensorBoard / WandB（学習中）

`biped_ppo_walk_env.py` の `extras["log"]` より:

| キー | 意味 |
|------|------|
| `Reward/mean_forward` | 前進報酬の平均 |
| `Reward/mean_effort` | エフォートペナルティ |
| `Metrics/mean_imu_x` | IMU 世界 X 座標 |
| `Metrics/mean_root_vel_x` | ルート +X 速度 |
| `Metrics/mean_upright` | 直立度（imu_zaxis の Z 成分） |
| `Metrics/left_contact_ratio` | 左足接地率 |
| `Metrics/right_contact_ratio` | 右足接地率 |
| `Metrics/single_support_ratio` | 片足支持率 |
| `Metrics/alternating_landing_ratio` | 交互着地率 |
| `Metrics/foot_swap_ratio` | 左右片脚切り替え率 |
| `Metrics/mean_same_side_streak` | 同側片脚連続ステップ |
| `Metrics/episode_displacement_x` | エピソード終了時の +X 移動距離 |

### eval_biped_walk.py

学習済み ckpt をロードし、移動距離・エピソード長・片脚率などを headless で集計します。

### Robotics Hub

`robotics-hub/server/isaac_rl_log_server.py` 経由で「Isaac 学習進捗」画面（`/isaac-rl-log`）に表示可能です。

---

## exp_030（MuJoCo）との対応表

| 領域 | MuJoCo exp_030 | Isaac Lab |
|------|----------------|-----------|
| 環境クラス | `sim/env.py` | `biped_ppo_walk_env.py` |
| 設定 | Hydra `conf/` | `biped_ppo_walk_env_cfg.py` |
| 報酬 | `sim/reward.py` | `mdp/reward.py` |
| 終了 | `sim/termination.py` | `mdp/termination.py` |
| 観測 | `sim/observation.py`（51 次元） | `biped_ppo_walk_env._get_observations`（54 次元） |
| 位相状態 | `sim/episode_state.py` | `mdp/episode_state.py` |
| 行動写像 | `lib/ctrl.py` | `mdp/action.py` |
| ロボット | `model/main.xml` | `assets/robots/yuuki_biped/main_isaac.xml` |
| 学習 | 自前 PPO + Hydra | RSL-RL PPO |
| チェックポイント | `mujoco_rl_sim/runs/exp_030_.../` | `isaac-lab/logs/rsl_rl/biped_ppo_walk/` |

報酬・終了の係数は `BipedRewardCfg` / `BipedTerminationCfg` に **Python のデフォルト値** として直書きされており、Hydra YAML によるランタイム override はありません。変更する場合は設定クラスを編集するか、今後 Hydra 連携を追加してください。

---

## 変更時のガイド

| 変えたい内容 | 触るファイル |
|-------------|-------------|
| 報酬係数・フラグ | `biped_ppo_walk_env_cfg.py` → `BipedRewardCfg` |
| 報酬ロジック | `mdp/reward.py` |
| 終了閾値 | `biped_ppo_walk_env_cfg.py` → `BipedTerminationCfg` |
| 観測次元・内容 | `biped_ppo_walk_env.py` の `_get_observations` + `observation_space` |
| 関節・ctrlrange | `mdp/actuators.py` + MJCF |
| 並列 env 数・物理 | `biped_ppo_walk_env_cfg.py` → `scene` / `sim` |
| PPO ハイパラ | `agents/rsl_rl_ppo_cfg.py` |
| Gym タスク ID | `__init__.py` |

観測次元を変えた場合は **新しい Task ID**（例: `...-v1`）で登録し直すことを推奨します（既存 ckpt との互換性のため）。

報酬・終了を変更したら、本 README と（可能なら）MuJoCo 側 [docs/experiments/exp_030_biped_ppo_walk/](../../../../../../../docs/experiments/exp_030_biped_ppo_walk/) の意図的差分もメモしておいてください。
