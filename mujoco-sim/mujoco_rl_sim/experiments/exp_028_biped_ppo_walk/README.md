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

人間・AI 共通の入口。**タスク仕様の詳細**（観測 idx 表・報酬式）は本 README と `python -m contract markdown`、**落とし穴**は [AGENTS.md](AGENTS.md) を参照。

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

## 報酬の要点

- `forward_imu` + `forward_foot`: `single_support` かつ `upright ≥ 0.62` のときのみ
- `double_support_penalty`: 両足接地中の前進（`dx` / 足 `dx`）に比例＋ベース
- `alternating_landing_bonus`: 反対脚支持からの着地エッジ
- `flight_duration_penalty`: 両足非接地が 4 step 超（ホップ抑制）
- `progress_bonus`: 片足支持時のみ IMU +X 最高値を更新

## 観測の追加（idx 12–14）

- 左/右足 site Z（正規化）
- 片足支持フラグ（+1 / それ以外 -1）

チェックポイント: `mujoco_rl_sim/runs/exp_028_biped_ppo_walk/`
