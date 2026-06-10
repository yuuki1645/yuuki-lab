# exp_030 — 報酬設計

実装の正本は **`sim/reward.py`**（`Reward.compute`）と **`conf/reward/*.yaml`**（ENABLE 群・係数）。  
歩行位相（片足支持・着地エッジ・飛翔ステップ数）は **`sim/episode_state.py`** が更新し、  
**`sim/env.py`** が報酬に加えて接触・姿勢終了ペナルティを合成する。

YAML キーは `reward.enable_*` / `reward.forward_*` 等（旧 `REWARD_ENABLE_*` の snake_case 版）。下表の「旧名」はコード内・dispatch キーとの対応用。

### 現行方針: ミニマル報酬（報酬地獄回避）

複数の shaping 項を同時に有効にすると係数干渉（報酬地獄）が起きやすいため、  
**`reward.enable_*` で項ごとに ON/OFF** し、まずは少数の主報酬だけで学習する（既定 preset: `reward=baseline`）。

**既定（ミニマル preset）で有効な項:**

| 項 | ENABLE（Hydra） | 意図 |
|----|-----------------|------|
| **forward_imu** | `reward.enable_forward=true` | 接地・直立時の IMU +X 移動に報酬（主報酬） |
| **effort_penalty** | `reward.enable_effort=true` | 筋力コストで無駄な動きを抑制 |
| 転倒終了ペナルティ | （常時・`termination.py`） | エピソード終了時のみ。ENABLE 対象外 |

**既定で無効な項:** 歩行 shaping（push/landing/交互着地/遊脚）、進捗、直立ボーナス、姿勢ペナルティ群、すり足・ホップ抑制、`forward_foot`。

前進ゲートもミニマル向けに緩和:

| 設定（Hydra） | 既定 | 備考 |
|---------------|------|------|
| `reward.forward_require_single_support` | `false` | `true` で片足支持時のみ前進（歩行 shaping 主線） |
| `reward.forward_imu_lean_gate` | `false` | `true` で飛翔中の前傾 IMU 前進を減衰 |
| `reward.forward_min_upright` | `0.50` | 歩行主線は `0.62` |

### ENABLE 群（`conf/reward/baseline.yaml`）

`sim/reward.py` の `compute()` 末尾で参照。`false` なら該当項は **0 固定**（係数 `*_scale` は温存）。

| Hydra キー | 旧 dispatch キー | 制御する報酬項 |
|------------|------------------|----------------|
| `reward.enable_forward` | `reward_enable_forward` | `forward_imu` |
| `reward.enable_forward_foot` | `reward_enable_forward_foot` | `forward_foot` |
| `reward.enable_progress` | `reward_enable_progress` | `progress_bonus` |
| `reward.enable_walk_shaping` | `reward_enable_walk_shaping` | `push_off_bonus`, `landing_bonus`, `alternating_landing_bonus`, `swing_clearance_bonus` |
| `reward.enable_upright_bonus` | `reward_enable_upright_bonus` | `upright_bonus` |
| `reward.enable_posture_penalties` | `reward_enable_posture_penalties` | 姿勢ペナルティ群 |
| `reward.enable_double_support` | `reward_enable_double_support` | `double_support_penalty` |
| `reward.enable_flight_duration` | `reward_enable_flight_duration` | `flight_duration_penalty` |
| `reward.enable_effort` | `reward_enable_effort` | `effort_penalty` |

**歩行 shaping 主線に戻す例:**

```bash
python train.py reward=walk_shaping_on \
  reward.forward_require_single_support=true \
  reward.forward_imu_lean_gate=true \
  reward.forward_min_upright=0.62
```

（`conf/reward/walk_shaping_on.yaml` は `baseline` を継承し shaping 群を ON）

dispatch sweep からも `DISPATCH_CONFIG_OVERRIDES_JSON` で上書き可能（`lib/dispatch_cfg_merge.DISPATCH_KEY_TO_CFG_PATH`）。

### 設計方針（exp_026 ホップ主線との差・参考）

歩行 shaping 主線を再有効化したときの狙い:

| 狙い | 手段 |
|------|------|
| **交互片脚歩行** | 前進報酬・進捗ボーナスは **片足支持時のみ**（`FORWARD_REQUIRE_SINGLE_SUPPORT`） |
| **すり足抑制** | 両足接地中の前進に `double_support_penalty`（`REWARD_ENABLE_DOUBLE_SUPPORT`） |
| **ホップ抑制** | 両足非接地が長続きすると `flight_duration_penalty`（`REWARD_ENABLE_FLIGHT_DURATION`） |
| **歩行位相の誘導** | push-off / landing / 交互着地 / 遊脚離地（`REWARD_ENABLE_WALK_SHAPING`） |
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
  upright ≥ FORWARD_MIN_UPRIGHT (既定 0.50)
  AND (任意足接地)           if FORWARD_REQUIRE_FOOT_CONTACT
  AND single_support         if FORWARD_REQUIRE_SINGLE_SUPPORT  # ミニマル preset: False
```

`FORWARD_IMU_LEAN_GATE=True` のとき、飛翔中（両足非接地）かつ `forward_allowed` のとき IMU 前進に **前傾ゲート** が掛かる（ミニマル preset では `False`）:

```text
imu_forward_scale = clip(1 - FORWARD_IMU_LEAN_GATE_SCALE * max(0, lean_fwd_body - THRESH), MIN_MULT, ∞)
forward_imu *= imu_forward_scale   # 前傾しすぎるホップ前進を減衰
```

### 報酬項一覧（`sim/reward.py`）

記号: `dx` = IMU +X 移動量/step、`stance_foot_dx` = 支持脚の +X 移動（片足支持時のみ）、  
`lean_fwd_body` / `heading_align` / `tilt_horiz` = `lib/pose.pose_metrics`、  
`upright` = IMU 上向き単位ベクトルの Z 成分。

#### 前進 `forward`（主報酬）

| 項 | 条件 | 式（既定係数） | YAML（`reward.*`） |
|----|------|----------------|--------|
| **forward_imu** | `forward_allowed` | `clip(dx, 0, MAX_DX) * FORWARD_REWARD_SCALE * imu_forward_scale` | `FORWARD_REWARD_SCALE=50` |
| **forward_foot** | `forward_allowed` かつ片足支持 | `clip(stance_foot_dx, 0, MAX_DX) * FORWARD_REWARD_SCALE` | 同上 |

`MAX_DX_PER_STEP = 0.05 * FRAME_SKIP`（1 制御ステップあたりのクリップ上限）。

#### 歩行 shaping ボーナス（`shaping` に加算）

| 項 | 条件 | 式 | YAML（`reward.*`） |
|----|------|-----|--------|
| **upright_bonus** | `dx ≥ UPRIGHT_BONUS_MIN_DX` | `max(0, upright - THRESH) * SCALE` | `THRESH=0.60`, `SCALE=0.8` |
| **push_off_bonus** | 片足支持、支持脚 `foot_dx ≥ MIN`、かつ（膝伸展速度 or IMU 上昇） | 定数 `PUSH_OFF_BONUS_SCALE` | `0.22` |
| **landing_bonus** | 着地エッジ、つま先・かかと Z が低く、前傾が抑えめ | 定数 `LANDING_BONUS_SCALE` | `0.35` |
| **alternating_landing_bonus** | `alternating_landing` | 定数 `ALTERNATING_LANDING_BONUS_SCALE` | `0.45` |
| **swing_clearance_bonus** | 片足支持、遊脚が床から `SWING_MIN_FOOT_Z` 以上 | `max(0, swing_foot_z - MIN) * SCALE` | `MIN=0.04`, `SCALE=0.12` |
| **progress_bonus** | `progress_m > 0`（片足支持・直立で最高 IMU X 更新） | `progress_m * PROGRESS_REWARD_SCALE` | `20.0` |

push-off の膝伸展判定: 支持脚の膝角速度 `qvel < -PUSH_OFF_MIN_KNEE_EXT_VEL`（伸展方向）。

#### shaping ペナルティ（`shaping` から減算）

| 項 | 条件 | 式 | YAML（`reward.*`） |
|----|------|-----|--------|
| **double_support_penalty** | 両足接地 | `max(dx, left_foot_dx, right_foot_dx の +X) * SCALE`、前進ほぼゼロなら `SCALE*0.25` | `SCALE=8.0` |
| **flight_duration_penalty** | 両足非接地 | `max(0, aerial_steps - AFTER) * SCALE` | `AFTER=4`, `SCALE=0.18` |
| **backward_lean_penalty** | 常時 | `max(0, -lean_fwd_body - THRESH) * SCALE` | `THRESH=0.12`, `SCALE=3.0` |
| **forward_lean_penalty** | 飛翔中かつ `aerial_steps ≥ MIN` | `max(0, lean_fwd_body - THRESH) * SCALE` | `THRESH=0.14`, `MIN_STEPS=2`, `SCALE=4.0` |
| **heading_misalign_penalty** | 常時 | `max(0, HEADING_ALIGN_MIN - heading_align) * SCALE` | `MIN=0.85`, `SCALE=1.5` |
| **lateral_tilt_penalty** | 常時 | `max(0, tilt_horiz - THRESH) * SCALE` | `THRESH=0.12`, `SCALE=2.5` |
| **height_penalty** | IMU 高さが姿勢別ターゲット未満 | `max(0, target_z - imu_z) * IMU_HEIGHT_PENALTY_SCALE`（飛翔クラッシュ時は ×1.5） | ターゲット: 片足 `0.50` / 両足 `0.52` / その他 `0.55` |
| **knee_hyperflex_penalty** | 飛翔中のみ（`AERIAL_ONLY=True`） | `max(0, max(knee_q) - MAX_RAD) * SCALE` | `MAX_RAD=0.95`, `SCALE=2.5` |

#### effort（ミニマル preset で ON）

| 項 | 式 | YAML（`reward.*`） |
|----|-----|--------|
| **effort_penalty** | 12 関節の `Σ |τ·q̇|/τ_max * dt` を制御ステップで積算 × `EFFORT_PENALTY_SCALE` | `REWARD_ENABLE_EFFORT=True`, `EFFORT_PENALTY_SCALE=3.0` |

### `env.py` で加算される項（`reward.py` 外）

| 項 | タイミング | 内容 |
|----|------------|------|
| **shank_penalty_sum** | 各物理ステップ | すね geom が床に触れたときのステップペナルティ（終了せず積算。詳細は [終了条件と終了ペナルティ](termination.md)） |
| **termination.penalty** | エピソード終了ステップ | 転倒・異常接触・姿勢不良で 1 回加算（同上） |

### Hub / W&B ログキー

契約上の主要キー（`contract/biped_walk_v1.py`）:  
`reward_total`, `reward_forward`, `reward_forward_imu`, `reward_forward_foot`, `reward_shaping`,  
`reward_double_support_penalty`, `reward_alternating_landing`, `reward_fall_penalty`, `reward_progress`。

`step_info` には上記 breakdown の各項が個別キーでも入る（`env.py` 参照）。

### sweep で触る係数・ENABLE

`DISPATCH_CONFIG_OVERRIDES_JSON`（`lib/dispatch_cfg_merge.py`）経由で上書き可能な代表例:

- `reward_enable_*`（各 ENABLE フラグ）
- `forward_reward_scale`, `forward_require_single_support`, `forward_imu_lean_gate`
- `double_support_penalty_scale`, `alternating_landing_bonus_scale`

詳細は [sweep.md](sweep.md) を参照。
