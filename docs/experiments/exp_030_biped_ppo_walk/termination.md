# exp_030 — 終了条件と終了ペナルティ

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
| 最大制御ステップ | `max_steps_per_episode = 1500` | `conf/training/prod.yaml`（`15_000 // frame_skip`） |
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
| `max_backward_lean_body` | **0.38** | `conf/termination/default.yaml`。`lean_fwd_body < -0.38` で後傾転倒 |
| `POSE_TERMINATION_PENALTY` | **-30.0** | 上記 3 理由共通の固定ペナルティ |

参考: 立位 keyframe の `imu_z ≈ 0.71 m`。転倒線 **0.30 m** は歩行目標 IMU（0.50〜0.55 m）より低い。Viewer では `termination.min_imu_z` / `min_imu_z_stance` から **薄赤の参考平面**を表示する（`sim/viewer_height_overlay.py`）。

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

`termination.contact_shank_terminates = false`（**exp_030 既定**）のとき:

| 項目 | 内容 |
|------|------|
| 対象 geom | `shank_link`, `right_shin_link`（`lib/actuators.SHANK_GEOM_IDS`） |
| タイミング | **各物理ステップ**（最大 `FRAME_SKIP=10` 回/制御ステップ） |
| 式 | `_shank_step_penalty` = `_floor_termination_penalty(F, scale=1.0)`（上式と同型） |
| 終了 | **しない**（`shank_penalty_sum` として `reward_total` に加算） |
| `contact_shank_terminates=true` | すね床接触で **`contact_shank` 終了**になり、ステップペナルティは **0**（二重計上回避） |

### 1 制御ステップあたりの報酬への影響

```text
reward_total = forward + shaping - effort_penalty
             + termination.penalty      # terminated ステップのみ（0 または ≤ -10 / -30 / 床接触式）
             + shank_penalty_sum        # すね接触の物理ステップ分（0 または各ステップ ≤ -20 程度）
```

`ppo.reward_clip=20` は PPO の GAE 計算前に **最終 `reward_total`** をクリップする（終了ペナルティ単体のクリップではない）。

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
| 姿勢閾値・固定ペナルティ | `conf/termination/default.yaml` + `sim/termination.py` |
| 後傾閾値 | `termination.max_backward_lean_body` |
| すねを終了にするか | `termination.contact_shank_terminates` |
| 床接触ペナルティ係数 | `sim/termination.py`（`_floor_termination_penalty` 内定数） |
| 監視対象 geom | `model/main.xml` + `lib/actuators.py` + `termination.py` |
| エピソード長 | `training.max_steps_per_episode` |
