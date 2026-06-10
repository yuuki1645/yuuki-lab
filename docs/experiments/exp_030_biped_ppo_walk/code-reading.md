# exp_030 — コードリーディングの手引き

人間・AI 共通の入口。**報酬**は [reward.md](reward.md)、**終了**は [termination.md](termination.md)、**観測 idx 表**は `python -m contract markdown`、**落とし穴**は [AGENTS.md](../../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/AGENTS.md)。

### 最初に押さえる 3 点

| 項目 | 場所 | 内容 |
|------|------|------|
| 係数・次元 | `conf/` + `ExperimentContext` | 報酬 scale、51 次元、方策 MLP、制御 50 Hz |
| 歩行の定義 | `sim/reward.py` + `sim/episode_state.py` | 片足支持ゲート、交互着地、すり足抑制 |
| 契約 | `contract/biped_walk_v1.py` | 観測スライス・テレメトリ schema `biped_walk_v1` |

### 推奨読み順（タスク理解）

目的別に **深掘りしたいファイルから逆順** に読んでもよい。

1. **`conf/config.yaml` + `conf/reward/`** … 何を学習させたいか（係数・ENABLE の一覧）
2. **`sim/episode_state.py`** … 片足支持・着地エッジ・交互着地・`aerial_steps` の更新
3. **`sim/reward.py`** … `Reward.compute` で前進/shaping を合成（歩行とホップの分岐点）
4. **`sim/observation.py`** … 51 次元 `PolicyObs` の組み立て・正規化
5. **`sim/termination.py`** … 転倒・床接触の終了条件（詳細は [termination.md](termination.md)）
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
| 報酬係数・ハイパラ | `conf/reward/*.yaml`（sweep は `DISPATCH_CONFIG_OVERRIDES_JSON`） |
| 歩行 shaping の式 | `sim/reward.py` |
| 観測次元・正規化 | `sim/observation.py` + `contract/biped_walk_v1.py` + `conf/sim/default.yaml` |
| 転倒条件 | `conf/termination/` + `sim/termination.py` |
| ロボット・接触 geom | `model/main.xml` + `lib/actuators.py` |
| 方策ネット | `rl/agent.py` + `conf/sim/default.yaml`（`policy_hidden_sizes`） |
| 学習ループ・warmup | `contract/session.py` + `sim/warmup.py` |
| Hub 表示 | `telemetry/` + `contract/telemetry.py` |

### エントリポイント早見

| コマンド | 入口 | 次に読む |
|----------|------|----------|
| `python train.py` | `train.py` → `run_ppo_train` | `contract/session.py` |
| `python visualize.py` | `visualize.py` → `EnvBipedPPO` | `sim/env.py` |
| `python -m contract markdown` | `contract/codegen.py` | `contract/biped_walk_v1.py` |
| AWS Spot 並列 | `scripts/aws_launch.py` | [aws/README.md](../../../mujoco-sim/aws/README.md) |
| ローカル並列 | `scripts/launch_parallel.ps1` | `runtime.num_envs` |
| sweep（LAN レガシー） | `dispatch` CLI | `lib/dispatch_cfg_merge.py` |

### 前後 exp との差分を追うとき

| 比較 | 見る場所 |
|------|----------|
| exp_026（ホップ主線） | `sim/reward.py` の `forward_allowed`・`double_support_penalty` 有無 |
| exp_029（コピー元・機能同一） | 本フォルダは runs 整理用 fork。差分は git diff で確認 |
| exp_008 系（片脚ホッパ） | **混同注意**: 飛翔中 IMU `dx` を主報酬に戻さない（[AGENTS.md](../../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/AGENTS.md)） |

観測 51 次元の idx 表は `contract/biped_walk_v1.py` か `python -m contract markdown` が正本。README の報酬節と併せて読む。
