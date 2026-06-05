# exp_028: 交互片脚歩行 PPO（exp_027 コピー）

**exp_027** と同一機能の作業用コピーです（報酬・観測・学習ループは同じ）。  
設計の源流は **exp_026** の MLP を維持した **交互片脚歩行** タスクです。

| 項目 | exp_026 | exp_028 |
|------|---------|---------|
| 前進報酬 | 飛翔中も IMU `dx`、両足 `foot_dx` 合算可 | **片足支持時のみ** |
| すり足 | 抑制なし | **`double_support_penalty`** |
| 位相 | push/landing 無効 | **push / landing / 交互着地 / 遊脚離地** |
| 観測 | 48 次元 `biped_ppo_v1` | **51 次元 `biped_walk_v1`** |

## 実行

```bash
cd exp_028_biped_ppo_walk
pip install -r requirements.txt
python train.py
python visualize.py
```

補助 CLI:

```bash
python scripts/analyze_rollout.py --checkpoint runs/.../final.pt
python scripts/preview_warmup.py
.\scripts\launch_parallel.ps1
```

契約表: `python -m contract markdown`

## ディレクトリ構成

| パス | 内容 |
|------|------|
| `train.py`, `visualize.py` | 学習・可視化の入口 |
| `config.py`, `package_meta.py`, `_paths.py` | 設定・パス |
| `sim/` | 環境・観測・報酬・終了・warmup |
| `rl/` | PPO・チェックポイント・run 設定・W&B |
| `scripts/` | ロールアウト解析・warmup プレビュー・並列学習 |
| `contract/` | 観測契約 `biped_walk_v1`・PPO ループ |
| `lib/` | ctrl・正規化・dispatch 上書き |
| `telemetry/`, `mujoco_sim_common/` | Hub・viewer 共有 |

## コードリーディングの手引き

人間・AI 共通の入口。**報酬設計**は本 README の「報酬設計」節、**観測 idx 表**は `python -m contract markdown`、**落とし穴**は [AGENTS.md](AGENTS.md) を参照。

### 最初に押さえる 3 点

| 項目 | 場所 | 内容 |
|------|------|------|
| 係数・次元 | `config.py` | 報酬 scale、51 次元、`POLICY_HIDDEN_SIZES`、制御 50 Hz |
| 歩行の定義 | `sim/reward.py` + `sim/episode_state.py` | 片足支持ゲート、交互着地、すり足抑制 |
| 契約 | `contract/biped_walk_v1.py` | 観測スライス・テレメトリ schema `biped_walk_v1` |

### 推奨読み順（タスク理解）

目的別に **深掘りしたいファイルから逆順** に読んでもよい。

1. **`config.py`** … 何を学習させたいか（係数の一覧）
2. **`sim/episode_state.py`** … 片足支持・着地エッジ・交互着地・`aerial_steps` の更新
3. **`sim/reward.py`** … `Reward.compute` で前進/shaping を合成（歩行とホップの分岐点）
4. **`sim/observation.py`** … 51 次元 `PolicyObs` の組み立て・正規化
5. **`sim/termination.py`** … 転倒・床接触の終了条件
6. **`sim/env.py`** … 上記を 1 制御ステップに束ねる（`step()` が中心）
7. **`train.py`** → **`contract/session.py`** … 学習ループ（薄い入口 + 共通 PPO ループ）
8. **`rl/agent.py`** … PPO 本体（exp_026 と同一 MLP 形状ならここは差分小）

### 1 制御ステップの流れ（`env.step`）

```
action [-1,1]^12
  → lib/action.py（stand keyframe 基準で ctrl 写像）
  → FRAME_SKIP 回 mj_step（sim/termination: 接触終了・すね step ペナルティ）
  → sim/observation.build（PolicyObs + StepPhysics）
  → sim/episode_state.advance_biped_context / advance_progress
  → sim/reward.compute
  → sim/termination.done_reason_pose
  → reward, obs_vector, step_info
```

学習時は `contract/session.py` がこれを `ROLLOUT_STEPS` 分繰り返し → `rl/agent.py` の `update()`。

### ディレクトリ × 変更したいとき

| 変更したい内容 | 触るファイル |
|----------------|--------------|
| 報酬係数・ハイパラ | `config.py`（sweep 対象は `lib/dispatch_config.py` も） |
| 歩行 shaping の式 | `sim/reward.py` |
| 観測次元・正規化 | `sim/observation.py` + `contract/biped_walk_v1.py` + `config.OBS_DIM` |
| 転倒条件 | `sim/termination.py` |
| ロボット・接触 geom | `model/main.xml` + `lib/actuators.py` |
| 方策ネット | `rl/agent.py` + `config.POLICY_HIDDEN_SIZES` |
| 学習ループ・warmup | `contract/session.py` + `sim/warmup.py` |
| Hub 表示 | `telemetry/` + `contract/telemetry.py` |

### エントリポイント早見

| コマンド | 入口 | 次に読む |
|----------|------|----------|
| `python train.py` | `train.py` → `run_ppo_train` | `contract/session.py` |
| `python visualize.py` | `visualize.py` → `EnvBipedPPO` | `sim/env.py` |
| `python -m contract markdown` | `contract/codegen.py` | `contract/biped_walk_v1.py` |
| sweep 並列 | `scripts/launch_parallel.ps1` | `lib/dispatch_config.py` |

### 前後 exp との差分を追うとき

| 比較 | 見る場所 |
|------|----------|
| exp_026（ホップ主線） | `sim/reward.py` の `forward_allowed`・`double_support_penalty` 有無 |
| exp_027（機能同一） | 本フォルダはコピー作業用。差分は git diff で確認 |
| exp_008 系（片脚ホッパ） | **混同注意**: 飛翔中 IMU `dx` を主報酬に戻さない（[AGENTS.md](AGENTS.md)） |

観測 51 次元の idx 表は `contract/biped_walk_v1.py` か `python -m contract markdown` が正本。README の報酬節と併せて読む。

## sweep（約 50 run）

```bash
python -m mujoco_rl_sim.dispatch.coordinator.cli plan --file sweeps/walk_reward_sweep_48.yaml
```

| 探索軸 | 値 | 意図 |
|--------|-----|------|
| `double_support_penalty_scale` | 4, 8, 14 | すり足抑制の強さ |
| `alternating_landing_bonus_scale` | 0.25, 0.55 | 左右交互着地 |
| `forward_reward_scale` | 40, 55 | 前進 vs shaping のバランス |
| seed | 1–4 | 12 設定 × 4 = **48 job** |

LR は `config.LR=2.5e-4` 固定（MLP 拡大時の exp_026 既定）。

## 報酬設計

実装の正本は **`sim/reward.py`**（`Reward.compute`）と **`config.py`**（係数）。  
歩行位相（片足支持・着地エッジ・飛翔ステップ数）は **`sim/episode_state.py`** が更新し、  
**`sim/env.py`** が報酬に加えて接触・姿勢終了ペナルティを合成する。

### 設計方針（exp_026 ホップ主線との差）

| 狙い | 手段 |
|------|------|
| **交互片脚歩行** | 前進報酬・進捗ボーナスは **片足支持時のみ**（`FORWARD_REQUIRE_SINGLE_SUPPORT`） |
| **すり足抑制** | 両足接地中の前進に `double_support_penalty` |
| **ホップ抑制** | 両足非接地が長続きすると `flight_duration_penalty`；飛翔中 IMU 前進はゲートで減衰 |
| **歩行位相の誘導** | push-off / landing / 交互着地 / 遊脚離地の shaping ボーナス |
| **転倒・異常姿勢** | `sim/termination.py` でエピソード終了＋終了ステップにペナルティ |

### 1 制御ステップあたりの合成式

制御周期は **50 Hz**（`CONTROL_TIMESTEP_S = 0.02 s`、1 行動 = `FRAME_SKIP=10` 物理ステップ）。

```
reward_total = forward + shaping - effort_penalty
             + termination.penalty      # env.py（終了ステップのみ）
             + shank_penalty_sum        # env.py（物理ステップごと積算）
```

`reward.py` 内の分解:

```
forward  = forward_imu + forward_foot
shaping  = (歩行ボーナス合計) - (姿勢・すり足・ホップ等ペナルティ合計)
total    = forward + shaping - effort_penalty   # reward.py 出力
```

PPO 学習時は `reward_total` が `agent.store` に渡る（`REWARD_CLIP=20` で GAE 計算前にクリップ）。

### 歩行位相（`episode_state.py`）

`advance_biped_context` が毎ステップ `BipedStepContext` を返す。報酬の多くがここに依存する。

| フィールド | 定義 |
|------------|------|
| `single_support` | 左右のどちらか 1 足だけ床接触 |
| `single_support_side` | 左支持 `+1` / 右支持 `-1` / それ以外 `0` |
| `both_feet_on_floor` | 両足接地 |
| `left_landed` / `right_landed` | 非接地→接地の **立ち上がりエッジ** |
| `alternating_landing` | 前ステップが反対脚支持だった状態からの着地（左着地←右支持、右着地←左支持） |
| `aerial_steps` | 両足非接地の連続ステップ数（接地で 0 にリセット） |

`advance_progress` はエピソード内 IMU +X の最高値 `best_imu_x` を更新し、  
`progress_m = max(0, imu_x - best_imu_x)` を返す（片足支持・`upright ≥ PROGRESS_MIN_UPRIGHT` のときのみカウント）。

### 前進ゲート `forward_allowed`

`forward_imu` / `forward_foot` / `progress_bonus` はすべてこのゲートの内側でのみ正の寄与がある（`progress` は `advance_progress` 側でも同条件）。

```text
forward_allowed =
  upright ≥ FORWARD_MIN_UPRIGHT (0.62)
  AND (任意足接地)           if FORWARD_REQUIRE_FOOT_CONTACT
  AND single_support         if FORWARD_REQUIRE_SINGLE_SUPPORT  # exp_028: True
```

飛翔中（両足非接地）かつ `forward_allowed` のとき、IMU 前進には **前傾ゲート** が掛かる:

```text
imu_forward_scale = clip(1 - FORWARD_IMU_LEAN_GATE_SCALE * max(0, lean_fwd_body - THRESH), MIN_MULT, ∞)
forward_imu *= imu_forward_scale   # 前傾しすぎるホップ前進を減衰
```

### 報酬項一覧（`sim/reward.py`）

記号: `dx` = IMU +X 移動量/step、`stance_foot_dx` = 支持脚の +X 移動（片足支持時のみ）、  
`lean_fwd_body` / `heading_align` / `tilt_horiz` = `lib/pose.pose_metrics`、  
`upright` = IMU 上向き単位ベクトルの Z 成分。

#### 前進 `forward`（主報酬）

| 項 | 条件 | 式（既定係数） | config |
|----|------|----------------|--------|
| **forward_imu** | `forward_allowed` | `clip(dx, 0, MAX_DX) * FORWARD_REWARD_SCALE * imu_forward_scale` | `FORWARD_REWARD_SCALE=50` |
| **forward_foot** | `forward_allowed` かつ片足支持 | `clip(stance_foot_dx, 0, MAX_DX) * FORWARD_REWARD_SCALE` | 同上 |

`MAX_DX_PER_STEP = 0.05 * FRAME_SKIP`（1 制御ステップあたりのクリップ上限）。

#### 歩行 shaping ボーナス（`shaping` に加算）

| 項 | 条件 | 式 | config |
|----|------|-----|--------|
| **upright_bonus** | `dx ≥ UPRIGHT_BONUS_MIN_DX` | `max(0, upright - THRESH) * SCALE` | `THRESH=0.60`, `SCALE=0.8` |
| **push_off_bonus** | 片足支持、支持脚 `foot_dx ≥ MIN`、かつ（膝伸展速度 or IMU 上昇） | 定数 `PUSH_OFF_BONUS_SCALE` | `0.22` |
| **landing_bonus** | 着地エッジ、つま先・かかと Z が低く、前傾が抑えめ | 定数 `LANDING_BONUS_SCALE` | `0.35` |
| **alternating_landing_bonus** | `alternating_landing` | 定数 `ALTERNATING_LANDING_BONUS_SCALE` | `0.45` |
| **swing_clearance_bonus** | 片足支持、遊脚が床から `SWING_MIN_FOOT_Z` 以上 | `max(0, swing_foot_z - MIN) * SCALE` | `MIN=0.04`, `SCALE=0.12` |
| **progress_bonus** | `progress_m > 0`（片足支持・直立で最高 IMU X 更新） | `progress_m * PROGRESS_REWARD_SCALE` | `20.0` |

push-off の膝伸展判定: 支持脚の膝角速度 `qvel < -PUSH_OFF_MIN_KNEE_EXT_VEL`（伸展方向）。

#### shaping ペナルティ（`shaping` から減算）

| 項 | 条件 | 式 | config |
|----|------|-----|--------|
| **double_support_penalty** | 両足接地 | `max(dx, left_foot_dx, right_foot_dx の +X) * SCALE`、前進ほぼゼロなら `SCALE*0.25` | `SCALE=8.0` |
| **flight_duration_penalty** | 両足非接地 | `max(0, aerial_steps - AFTER) * SCALE` | `AFTER=4`, `SCALE=0.18` |
| **backward_lean_penalty** | 常時 | `max(0, -lean_fwd_body - THRESH) * SCALE` | `THRESH=0.12`, `SCALE=3.0` |
| **forward_lean_penalty** | 飛翔中かつ `aerial_steps ≥ MIN` | `max(0, lean_fwd_body - THRESH) * SCALE` | `THRESH=0.14`, `MIN_STEPS=2`, `SCALE=4.0` |
| **heading_misalign_penalty** | 常時 | `max(0, HEADING_ALIGN_MIN - heading_align) * SCALE` | `MIN=0.85`, `SCALE=1.5` |
| **lateral_tilt_penalty** | 常時 | `max(0, tilt_horiz - THRESH) * SCALE` | `THRESH=0.12`, `SCALE=2.5` |
| **height_penalty** | IMU 高さが姿勢別ターゲット未満 | `max(0, target_z - imu_z) * IMU_HEIGHT_PENALTY_SCALE`（飛翔クラッシュ時は ×1.5） | ターゲット: 片足 `0.50` / 両足 `0.52` / その他 `0.55` |
| **knee_hyperflex_penalty** | 飛翔中のみ（`AERIAL_ONLY=True`） | `max(0, max(knee_q) - MAX_RAD) * SCALE` | `MAX_RAD=0.95`, `SCALE=2.5` |

#### effort（既定オフ）

| 項 | 式 | config |
|----|-----|--------|
| **effort_penalty** | 12 関節の `Σ |τ·q̇|/τ_max * dt` を制御ステップで積算 × `EFFORT_PENALTY_SCALE` | `APPLY_EFFORT_PENALTY=False`（exp_028 既定） |

### `env.py` で加算される項（`reward.py` 外）

| 項 | タイミング | 内容 |
|----|------------|------|
| **shank_penalty_sum** | 各物理ステップ | すね geom が床に触れたときのステップペナルティ（`CONTACT_SHANK_TERMINATES=False` のとき終了せず積算） |
| **termination.penalty** | エピソード終了ステップ | 床接触（バスケット・大腿）または姿勢不良（低 IMU Z / 低 upright / 後傾）で `-20〜` 〜 `-30` 程度 |

姿勢終了の閾値は `sim/termination.py` の `done_reason_pose`（例: `MIN_IMU_Z=0.40`、`MIN_IMU_UPRIGHT=0.52`）。

### Hub / W&B ログキー

契約上の主要キー（`contract/biped_walk_v1.py`）:  
`reward_total`, `reward_forward`, `reward_forward_imu`, `reward_forward_foot`, `reward_shaping`,  
`reward_double_support_penalty`, `reward_alternating_landing`, `reward_fall_penalty`, `reward_progress`。

`step_info` には上記 breakdown の各項が個別キーでも入る（`env.py` 参照）。

### sweep で触る係数

`lib/dispatch_config.SWEEPABLE_CONFIG_KEYS` 経由で上書き可能な代表例:

- `double_support_penalty_scale`
- `alternating_landing_bonus_scale`
- `forward_reward_scale`

詳細は [sweep 節](#sweep約-50-run) を参照。

## 観測の追加（idx 12–14）

- 左/右足 site Z（正規化）
- 片足支持フラグ（+1 / それ以外 -1）

チェックポイント: `mujoco_rl_sim/runs/exp_028_biped_ppo_walk/`
