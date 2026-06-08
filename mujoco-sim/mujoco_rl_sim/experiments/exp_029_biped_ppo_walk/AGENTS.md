# Cursor / AI エージェント向け — exp_029

## 位置づけ

- **由来**: [exp_028](../exp_028_biped_ppo_walk/) をコピー（コピー時点で機能同一。`runs/` 混在整理のため fork）
- **ベース**: [exp_026](../exp_026_biped_ppo_hop_balance/)（MLP 256→256→128）
- **差分**: ホップ/すり足ではなく **交互片脚歩行** 向けの報酬・観測（`biped_walk_v1`、51 次元）
- **実行**: 本フォルダで `python train.py`（`@hydra.main`）/ `python visualize.py --checkpoint <run>/final.pt`
- **レイアウト**: 本体は `sim/`（環境・報酬・観測）と `rl/`（PPO・ckpt）。設定は **`conf/` + `lib/experiment_context.py`（DI）**。補助は `scripts/`。ルートは `train.py` / `visualize.py` など入口のみ。**`config.py` は廃止**
- **ワークフロー**: [README.md](README.md) の「強化学習実験ワークフロー（exp_029）」が標準手順の正本
- **Hydra**: [README.md](README.md) の「Hydra 設定」節が config groups・override・再現の正本
- **コードリーディング**: 詳細手引きは [README.md](README.md) の「コードリーディングの手引き」（本 AGENTS.md には落とし穴のみ）
- **報酬設計**: 全文は [README.md](README.md) の「報酬設計」節（`sim/reward.py` + `conf/reward/`）
- **終了条件**: 全文は [README.md](README.md) の「終了条件と終了ペナルティ」節（`sim/termination.py` + `conf/termination/`）
- **契約**: `contract.TELEMETRY_CONTRACT`（= `BIPED_WALK_V1`）
- **チェックポイント**: `mujoco_rl_sim/runs/exp_029_biped_ppo_walk/`（**新規。exp_028 の runs は参照しない**）
- **run 再現**: `runs/<run>/.hydra/config.yaml`（旧 `config_effective.json` は廃止・再現対象外）
- **評価**: 学習終了後に自動 eval（`training.post_train_eval` 既定 true）。手動: `python scripts/eval.py --checkpoint <run>/final.pt`。横断比較: `python scripts/eval_compare.py`。スキップ: `training.post_train_eval=false`

## 歩行タスクの定義

- **片足支持**（左右どちらか 1 本だけ接地）のときのみ `forward_imu` / `forward_foot` / `progress`
- **両足接地**中の前進は `double_support_penalty` で抑制（すり足防止）
- **両足非接地**が長いと `flight_duration_penalty`（ホップ抑制）
- **交互着地** `alternating_landing_bonus`、支持脚 **push_off** / **landing**、遊脚 **swing_clearance**

## Hydra（エージェント向け要点）

- **既定起動**: `python train.py` → `training=prod`, `runtime=fast`, `wandb=enabled`, `reward=baseline`
- **スモーク**: `python train.py training=smoke runtime=fast wandb=disabled`
- **仮説 1 軸**: preset（`reward=forward55`）または **単一キー** override（`reward.forward_reward_scale=55`）
- **設定変更**: `conf/**/*.yaml` を編集するか CLI override。コード内の `import config` は **存在しない**
- **派生値**: YAML = 入力、`conf/schema/app_config.py` の `@property` = 派生（例: `max_steps_per_episode`）
- **Subproc VecEnv**: W&B init → run dir 確定 → `.hydra/config.yaml` 保存 → 子に yaml パス渡し
- **eval / visualize**: ckpt 親 run の `.hydra/` から `ExperimentContext` 復元（eval 試行条件は `eval/` 固定）

## sweep（dispatch）

- **本線**: `sweeps/walk_reward_sweep_48.yaml`（48 run）  
  `double_support_penalty_scale` × `alternating_landing_bonus_scale` × `forward_reward_scale`、LR 固定
- **スモーク**: `sweeps/baseline_10seed.yaml`（既定報酬 10 seed）
- 報酬係数は `DISPATCH_CONFIG_OVERRIDES_JSON` → `lib/dispatch_cfg_merge.py` で Hydra ネストパスへマージ（dispatch 本体は未改修）
- legacy job argv（`--set` 等）は `lib/dispatch_argv_bridge.py` が Hydra override に変換

## 変更時の注意

- 新 exp 派生時: [experiments/AGENTS.md](../AGENTS.md) の「新 exp 作成時 — README.md に書くこと」に従い README を更新（**報酬設計・終了条件節を必ず**、AGENTS へ長文を複製しない）
- 観測次元を変える場合は `contract/biped_walk_v1.py` + `conf/sim/default.yaml`（`obs_dim`）+ `contract validate`
- sweep に載せるキーは `lib/dispatch_cfg_merge.DISPATCH_KEY_TO_CFG_PATH` に追加
- exp_026 / exp_028 のチェックポイントは **観測 48→51** のためそのまま読めない（同一 51 次元なら exp_028 ckpt は resume 可）
- 飛翔中の IMU `dx` を主報酬に戻さない（exp_008 ホッパ主線と混同しない）
- Hydra は `outputs/` に実行ログを残すことがある（`hydra.job.chdir=false` でも）。成果物の正本は **`runs/.../.hydra/` + ckpt**
