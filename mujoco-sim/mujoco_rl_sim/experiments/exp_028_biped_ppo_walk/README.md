# exp_028: 交互片脚歩行 PPO（exp_027 コピー）

**exp_027** をコピーした作業用 fork です。**既定 `config.py` はミニマル報酬 preset**（`REWARD_ENABLE_WALK_SHAPING` 等が無効）で、exp_027 の歩行 shaping 主線とは異なります。  
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
python scripts/analyze_rollout.py --checkpoint run_YYYYMMDD_HHMMSS/final.pt
python scripts/eval.py --checkpoint run_YYYYMMDD_HHMMSS/final.pt
python scripts/preview_warmup.py
.\scripts\launch_parallel.ps1
```

契約表: `python -m contract markdown`

## 評価仕様（evaluation setup）

学習済みチェックポイントを **固定条件** で採点し、`eval_report.json` を出力する。  
sweep ランキング用ではなく、**1 ckpt の性能を mean ± std で把握**するのが目的。

| 項目 | v0（開発用） |
|------|----------------|
| 仕様 ID | `biped_walk_eval_v0`（`eval/spec.py`） |
| 試行数 | **5 seed × 3 ep = 15** |
| eval_seeds | `101, 102, 103, 104, 105` |
| ポリシー | **deterministic**（`act_eval`） |
| warmup | **False**（学習と同じ） |
| エピソード長 | `MAX_STEPS_PER_EPISODE`（30 s） |

### 初期姿勢ノイズ（eval のみ・`stand` keyframe 適用後）

| 対象 | ノイズ |
|------|--------|
| ルート X/Y 位置 | **なし**（平面タスク） |
| ルートヨー | ±3° |
| 関節角 12 DOF | ±2°（`jnt_range` でクリップ） |
| ルート線速度 | 各軸 ±0.05 m/s |
| ルート角速度 | 各軸 ±0.1 rad/s |

RNG: `np.random.default_rng([eval_seed, ep_index])`（15 試行すべて別ノイズ）。  
`origin_imu_x` は **ノイズ適用後** の IMU 世界 X。

### 主指標・副指標

| 種別 | 指標 |
|------|------|
| **Primary** | `displacement_x = final_imu_x - origin_imu_x` の mean |
| 統計量 | mean, std, min, max, 95%CI（全 15 試行） |
| Secondary | `episode_length`, `truncated_rate`, `termination_breakdown`, `alternating_landing_rate`, `single_support_ratio`, `double_support_ratio` |

### 実行・出力

```bash
python scripts/eval.py --checkpoint run_YYYYMMDD_HHMMSS/final.pt
# 省略時: <checkpoint 親>/eval_report.json
python scripts/eval.py --checkpoint ... --out path/to/eval_report.json
```

| ツール | 用途 |
|--------|------|
| `scripts/eval.py` | 公式採点（統計・JSON） |
| `scripts/analyze_rollout.py` | デバッグ（時系列 JSON・代表フレーム PNG） |

v0 は **手動 CLI・JSON のみ**（W&B / dispatch 連携は未実装）。

## ディレクトリ構成

| パス | 内容 |
|------|------|
| `train.py`, `visualize.py` | 学習・可視化の入口 |
| `config.py`, `package_meta.py`, `_paths.py` | 設定・パス |
| `sim/` | 環境・観測・報酬・終了・warmup |
| `rl/` | PPO・チェックポイント・run 設定・W&B |
| `eval/` | チェックポイント評価（仕様・ノイズ・集計・レポート） |
| `scripts/` | `eval.py`・ロールアウト解析・warmup プレビュー・並列学習 |
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
5. **`sim/termination.py`** … 転倒・床接触の終了条件（詳細は README「終了条件と終了ペナルティ」）
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
| 転倒条件 | `sim/termination.py`（README「終了条件と終了ペナルティ」が正本） |
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

実装の正本は **`sim/reward.py`**（`Reward.compute`）と **`config.py`**（ENABLE 群・係数）。  
歩行位相（片足支持・着地エッジ・飛翔ステップ数）は **`sim/episode_state.py`** が更新し、  
**`sim/env.py`** が報酬に加えて接触・姿勢終了ペナルティを合成する。

### 現行方針: ミニマル報酬（報酬地獄回避）

複数の shaping 項を同時に有効にすると係数干渉（報酬地獄）が起きやすいため、  
**`config.py` の `REWARD_ENABLE_*` で項ごとに ON/OFF** し、まずは少数の主報酬だけで学習する。

**既定（ミニマル preset）で有効な項:**

| 項 | ENABLE | 意図 |
|----|--------|------|
| **forward_imu** | `REWARD_ENABLE_FORWARD=True` | 接地・直立時の IMU +X 移動に報酬（主報酬） |
| **effort_penalty** | `REWARD_ENABLE_EFFORT=True` | 筋力コストで無駄な動きを抑制 |
| 転倒終了ペナルティ | （常時・`termination.py`） | エピソード終了時のみ。ENABLE 対象外 |

**既定で無効な項:** 歩行 shaping（push/landing/交互着地/遊脚）、進捗、直立ボーナス、姿勢ペナルティ群、すり足・ホップ抑制、`forward_foot`。

前進ゲートもミニマル向けに緩和:

| 設定 | 既定 | 備考 |
|------|------|------|
| `FORWARD_REQUIRE_SINGLE_SUPPORT` | `False` | `True` に戻すと片足支持時のみ前進（旧・歩行 shaping 主線） |
| `FORWARD_IMU_LEAN_GATE` | `False` | `True` で飛翔中の前傾 IMU 前進を減衰 |
| `FORWARD_MIN_UPRIGHT` | `0.50` | 旧主線は `0.62` |

### REWARD_ENABLE 群（`config.py`）

`sim/reward.py` の `compute()` 末尾で参照。`False` なら該当項は **0 固定**（係数 `*_SCALE` は温存）。

| config フラグ | 制御する報酬項 |
|---------------|----------------|
| `REWARD_ENABLE_FORWARD` | `forward_imu` |
| `REWARD_ENABLE_FORWARD_FOOT` | `forward_foot` |
| `REWARD_ENABLE_PROGRESS` | `progress_bonus` |
| `REWARD_ENABLE_WALK_SHAPING` | `push_off_bonus`, `landing_bonus`, `alternating_landing_bonus`, `swing_clearance_bonus` |
| `REWARD_ENABLE_UPRIGHT_BONUS` | `upright_bonus` |
| `REWARD_ENABLE_POSTURE_PENALTIES` | `backward_lean_penalty`, `forward_lean_penalty`, `heading_misalign_penalty`, `lateral_tilt_penalty`, `height_penalty`, `knee_hyperflex_penalty` |
| `REWARD_ENABLE_DOUBLE_SUPPORT` | `double_support_penalty` |
| `REWARD_ENABLE_FLIGHT_DURATION` | `flight_duration_penalty` |
| `REWARD_ENABLE_EFFORT` | `effort_penalty` |

**歩行 shaping 主線に戻す例**（`config.py` で書き換え）:

```python
REWARD_ENABLE_FORWARD = True
REWARD_ENABLE_FORWARD_FOOT = True
REWARD_ENABLE_PROGRESS = True
REWARD_ENABLE_WALK_SHAPING = True
REWARD_ENABLE_DOUBLE_SUPPORT = True
REWARD_ENABLE_FLIGHT_DURATION = True
FORWARD_REQUIRE_SINGLE_SUPPORT = True
FORWARD_IMU_LEAN_GATE = True
FORWARD_MIN_UPRIGHT = 0.62
```

dispatch sweep からも上書き可能（`lib/dispatch_config.SWEEPABLE_CONFIG_KEYS` に登録済み）。

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

#### effort（ミニマル preset で ON）

| 項 | 式 | config |
|----|-----|--------|
| **effort_penalty** | 12 関節の `Σ |τ·q̇|/τ_max * dt` を制御ステップで積算 × `EFFORT_PENALTY_SCALE` | `REWARD_ENABLE_EFFORT=True`, `EFFORT_PENALTY_SCALE=3.0` |

### `env.py` で加算される項（`reward.py` 外）

| 項 | タイミング | 内容 |
|----|------------|------|
| **shank_penalty_sum** | 各物理ステップ | すね geom が床に触れたときのステップペナルティ（終了せず積算。詳細は [終了条件と終了ペナルティ](#終了条件と終了ペナルティ)） |
| **termination.penalty** | エピソード終了ステップ | 転倒・異常接触・姿勢不良で 1 回加算（同上） |

### Hub / W&B ログキー

契約上の主要キー（`contract/biped_walk_v1.py`）:  
`reward_total`, `reward_forward`, `reward_forward_imu`, `reward_forward_foot`, `reward_shaping`,  
`reward_double_support_penalty`, `reward_alternating_landing`, `reward_fall_penalty`, `reward_progress`。

`step_info` には上記 breakdown の各項が個別キーでも入る（`env.py` 参照）。

### sweep で触る係数・ENABLE

`lib/dispatch_config.SWEEPABLE_CONFIG_KEYS` 経由で上書き可能な代表例:

- `reward_enable_*`（各 ENABLE フラグ）
- `forward_reward_scale`, `forward_require_single_support`, `forward_imu_lean_gate`
- `double_support_penalty_scale`, `alternating_landing_bonus_scale`

詳細は [sweep 節](#sweep約-50-run) を参照。

## 終了条件と終了ペナルティ

実装の正本は **`sim/termination.py`**。  
**`sim/env.py`** が 1 制御ステップ内で終了判定とペナルティ合成を行い、**`contract/session.py`** がエピソード打ち切り（truncation）を付ける。

`REWARD_ENABLE_*` の ON/OFF とは無関係に、**転倒・異常接触の終了判定は常時有効**。

### 用語

| 用語 | 意味 |
|------|------|
| **terminated** | `sim/termination.py` が検出した早期終了（転倒・異常接触・姿勢不良） |
| **truncated** | `MAX_STEPS_PER_EPISODE` 到達による打ち切り（`contract/session.py`）。**終了ペナルティなし** |
| **termination_reason** | 早期終了の理由文字列。truncated のみのときは `None` のまま（W&B 側で `truncated` と区別） |

### 評価タイミング（`env.step` 内）

```
FRAME_SKIP 回 mj_step のループ（各物理ステップ 500 Hz）:
  1. done_reason_contact   … バスケット・大腿（＋任意ですね）の床接触 → 即 break
  2. shank_contact_step_penalty … すね床接触のステップペナルティを積算（終了しない）

物理積分後（1 制御ステップ 50 Hz あたり 1 回）:
  3. done_reason_pose      … 低 IMU 高さ / 低 upright / 後傾（接触終了が無いときのみ）

reward_total += termination.penalty   # 終了ステップのみ（terminated のとき）
reward_total += shank_penalty_sum     # そのステップで触れた物理ステップ分をすべて加算
```

姿勢終了は **接触終了のあとに上書きされない**（接触で既に `terminated` なら `done_reason_pose` は呼ばれない）。

### エピソード打ち切り（truncation）

| 項目 | 値 | 所在 |
|------|-----|------|
| 最大制御ステップ | `MAX_STEPS_PER_EPISODE = 1500` | `config.py`（`15_000 // FRAME_SKIP`） |
| 相当シミュ時間 | **30 s** | `1500 × CONTROL_TIMESTEP_S`（50 Hz） |
| ペナルティ | **0** | truncation は `termination.penalty` を加算しない |

### 終了理由一覧

| `termination_reason` | 種別 | 発火条件 | 終了ペナルティ | 実装 |
|--------------------|------|----------|----------------|------|
| `contact_basket` | 接触 | `basket` geom が `floor` と接触 | 下式・`scale=1.0` | `done_reason_contact` |
| `contact_thigh` | 接触 | `thigh_link` / `right_thigh_link` が床接触 | 下式・`scale=0.5` | 同上 |
| `contact_shank` | 接触 | すね geom が床接触 | 下式・`scale=0.5` | **`CONTACT_SHANK_TERMINATES=True` のときのみ**（既定 `False`） |
| `imu_z` | 姿勢 | `imu_site` 世界 Z が下限未満 | **-30.0** 固定 | `done_reason_pose` |
| `low_upright` | 姿勢 | IMU 上向き成分 `upright < 0.52` | **-30.0** 固定 | 同上 |
| `backward_lean` | 姿勢 | ボディ +X 後傾 `lean_fwd_body < -MAX_BACKWARD_LEAN_BODY` | **-30.0** 固定 | 同上 |
| （truncated） | 打切 | ステップ数上限 | **0** | `contract/session.py` |

接触判定は **geom ペアの MuJoCo 接触**（`data.contact`）。足の接地判定（報酬ゲート用）と同じく `foot_plate` / `right_foot_plate` と床の接触を見るが、**足 geom の床接触自体は終了条件に含めない**（正常歩行）。

### 姿勢終了の閾値（`done_reason_pose`）

測定 site・センサ:

| 信号 | 取得元 | 単位 |
|------|--------|------|
| `imu_z` | `imu_site.xpos[2]` | 世界 Z [m]（床 = 0） |
| `upright` | `imu_zaxis` センサの Z 成分 | 無次元（直立 ≈ 1） |
| `lean_fwd_body` | `lib/pose.pose_metrics`（ボディ +X への IMU 前傾射影） | 無次元（後傾で負） |

| 定数 | 既定値 | 意味 |
|------|--------|------|
| `MIN_IMU_Z` | **0.30 m** | **両足非接地**（どちらの `foot_plate` も床と非接触）のときの IMU 下限 |
| `MIN_IMU_Z_STANCE` | **0.30 m** | **どちらか足が床接地**のときの IMU 下限（非接地時と同一） |
| `MIN_IMU_UPRIGHT` | **0.52** | これ未満で転倒扱い（`FORWARD_MIN_UPRIGHT=0.50` より厳しい） |
| `MAX_BACKWARD_LEAN_BODY` | **0.38** | `config.py`。`lean_fwd_body < -0.38` で後傾転倒 |
| `POSE_TERMINATION_PENALTY` | **-30.0** | 上記 3 理由共通の固定ペナルティ |

参考: 立位 keyframe の `imu_z ≈ 0.71 m`。転倒線 **0.30 m** は歩行目標 IMU（0.50〜0.55 m）より低い。Viewer では同じ高さに **薄赤の参考平面**（`config.VIEWER_TARGET_HEIGHT_PLANES`）を表示する。

### 床接触終了ペナルティの式（`_floor_termination_penalty`）

法線力 `F` [N] = 該当 geom と床の接触の **|force[0]| の最大値**（`mj_contactForce`）。

```text
excess_F = clip(F - FLOOR_MIN_FORCE_N, 0, FLOOR_FORCE_CAP_N - FLOOR_MIN_FORCE_N)
penalty  = clip(scale * (FLOOR_PENALTY_BASE + FLOOR_PENALTY_PER_N * excess_F),
                 scale * FLOOR_PENALTY_MIN, +∞)
```

| 定数 | 値 | 備考 |
|------|-----|------|
| `FLOOR_PENALTY_BASE` | **-20.0** | 接触検出時のベース |
| `FLOOR_PENALTY_PER_N` | **-0.016** / N | 力が大きいほど追加ペナルティ |
| `FLOOR_MIN_FORCE_N` | 0.0 | |
| `FLOOR_FORCE_CAP_N` | 10_000 | 力のクリップ上限 |
| `FLOOR_PENALTY_MIN` | **-200.0** | 1 回の下限（`scale=1` 時） |

`scale` の取り方:

| 理由 | `scale` | 力ゼロ付近の例 |
|------|---------|----------------|
| `contact_basket` | **1.0** | **-20** |
| `contact_thigh` / `contact_shank` | **0.5** | **-10** |

例: バスケット接触で法線力 500 N →  
`penalty = 1.0 × (-20 + (-0.016)×500) = -28`（下限 -200 まで）。

### すね接触ステップペナルティ（終了しない）

`config.CONTACT_SHANK_TERMINATES = False`（**exp_028 既定**）のとき:

| 項目 | 内容 |
|------|------|
| 対象 geom | `shank_link`, `right_shin_link`（`lib/actuators.SHANK_GEOM_IDS`） |
| タイミング | **各物理ステップ**（最大 `FRAME_SKIP=10` 回/制御ステップ） |
| 式 | `_shank_step_penalty` = `_floor_termination_penalty(F, scale=1.0)`（上式と同型） |
| 終了 | **しない**（`shank_penalty_sum` として `reward_total` に加算） |
| `CONTACT_SHANK_TERMINATES=True` | すね床接触で **`contact_shank` 終了**になり、ステップペナルティは **0**（二重計上回避） |

### 1 制御ステップあたりの報酬への影響

```text
reward_total = forward + shaping - effort_penalty
             + termination.penalty      # terminated ステップのみ（0 または ≤ -10 / -30 / 床接触式）
             + shank_penalty_sum        # すね接触の物理ステップ分（0 または各ステップ ≤ -20 程度）
```

`REWARD_CLIP=20` は PPO の GAE 計算前に **最終 `reward_total`** をクリップする（終了ペナルティ単体のクリップではない）。

### `step_info` / W&B ログキー

| キー | 内容 |
|------|------|
| `terminated` | 早期終了フラグ |
| `truncated` | env 単体では常に `False`（session が truncation を付与） |
| `termination_reason` | 上表の reason または `None` |
| `is_fallen` | `terminated` と同値 |
| `reward_termination_penalty` | そのステップの `termination.penalty` |
| `reward_contact_basket_penalty` | reason が `contact_basket` のときのみ |
| `reward_contact_thigh_penalty` | reason が `contact_thigh` のときのみ |
| `reward_contact_shank_penalty` | **`shank_penalty_sum`**（終了理由が shank でも step 積算分） |
| `reward_pose_penalty` / `reward_fall_penalty` | reason が `imu_z` / `low_upright` / `backward_lean` のとき |
| `contact_normal_force_n` | 接触終了時の法線力 [N] |
| `basket_contact_normal_force_n` / `thigh_contact_normal_force_n` | 理由別 |

W&B エピソード集計: `episode/terminate_imu_z`, `episode/terminate_low_upright`, `episode/terminate_backward_lean`, `episode/terminate_contact_basket`, `episode/terminate_contact_thigh`, `termination/rate_*` 等（`rl/wandb_logging.py`）。

### 変更したいとき

| 変更内容 | 触るファイル |
|----------|--------------|
| 姿勢閾値・固定ペナルティ | `sim/termination.py`（`done_reason_pose` 内定数） |
| 後傾閾値のみ config 化 | `config.MAX_BACKWARD_LEAN_BODY` |
| すねを終了にするか | `config.CONTACT_SHANK_TERMINATES` |
| 床接触ペナルティ係数 | `sim/termination.py`（`_floor_termination_penalty` 内定数） |
| 監視対象 geom | `model/main.xml` + `lib/actuators.py` + `termination.py` |
| エピソード長 | `config.MAX_STEPS_PER_EPISODE` |

## 観測の追加（idx 12–14）

- 左/右足 site Z（正規化）
- 片足支持フラグ（+1 / それ以外 -1）

チェックポイント: `mujoco_rl_sim/runs/exp_028_biped_ppo_walk/`
