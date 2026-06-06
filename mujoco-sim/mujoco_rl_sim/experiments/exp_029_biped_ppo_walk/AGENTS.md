# Cursor / AI エージェント向け — exp_029

## 位置づけ

- **由来**: [exp_028](../exp_028_biped_ppo_walk/) をコピー（コピー時点で機能同一。`runs/` 混在整理のため fork）
- **ベース**: [exp_026](../exp_026_biped_ppo_hop_balance/)（MLP 256→256→128）
- **差分**: ホップ/すり足ではなく **交互片脚歩行** 向けの報酬・観測（`biped_walk_v1`、51 次元）
- **実行**: 本フォルダで `python train.py` / `python visualize.py`
- **レイアウト**: 本体は `sim/`（環境・報酬・観測）と `rl/`（PPO・ckpt）。補助は `scripts/`。ルートは `train.py` / `visualize.py` / `config.py` など入口のみ
- **コードリーディング**: 詳細手引きは [README.md](README.md) の「コードリーディングの手引き」（本 AGENTS.md には落とし穴のみ）
- **報酬設計**: 全文は [README.md](README.md) の「報酬設計」節（`sim/reward.py` の正本ドキュメント）
- **終了条件**: 全文は [README.md](README.md) の「終了条件と終了ペナルティ」節（`sim/termination.py` の正本ドキュメント）
- **契約**: `contract.TELEMETRY_CONTRACT`（= `BIPED_WALK_V1`）
- **チェックポイント**: `mujoco_rl_sim/runs/exp_029_biped_ppo_walk/`（**新規。exp_028 の runs は参照しない**）
- **評価**: 学習終了後に自動 eval（`train.py` 既定）。手動: `python scripts/eval.py --checkpoint <run>/final.pt`。横断比較: `python scripts/eval_compare.py`。スキップ: `--no-eval`

## 歩行タスクの定義

- **片足支持**（左右どちらか 1 本だけ接地）のときのみ `forward_imu` / `forward_foot` / `progress`
- **両足接地**中の前進は `double_support_penalty` で抑制（すり足防止）
- **両足非接地**が長いと `flight_duration_penalty`（ホップ抑制）
- **交互着地** `alternating_landing_bonus`、支持脚 **push_off** / **landing**、遊脚 **swing_clearance**

## sweep（dispatch）

- **本線**: `sweeps/walk_reward_sweep_48.yaml`（48 run）  
  `double_support_penalty_scale` × `alternating_landing_bonus_scale` × `forward_reward_scale`、LR 固定
- **スモーク**: `sweeps/baseline_10seed.yaml`（既定報酬 10 seed）
- 報酬係数は `DISPATCH_CONFIG_OVERRIDES_JSON` → `lib/dispatch_config.py` で `config` に反映

## 変更時の注意

- 新 exp 派生時: [experiments/AGENTS.md](../AGENTS.md) の「新 exp 作成時 — README.md に書くこと」に従い README を更新（**報酬設計・終了条件節を必ず**、AGENTS へ長文を複製しない）
- 観測次元を変える場合は `contract/biped_walk_v1.py` + `config.OBS_DIM` + `contract/validate`
- sweep に載せるキーは `lib/dispatch_config.SWEEPABLE_CONFIG_KEYS` に追加
- exp_026 / exp_028 のチェックポイントは **観測 48→51** のためそのまま読めない（同一 51 次元なら exp_028 ckpt は resume 可）
- 飛翔中の IMU `dx` を主報酬に戻さない（exp_008 ホッパ主線と混同しない）
