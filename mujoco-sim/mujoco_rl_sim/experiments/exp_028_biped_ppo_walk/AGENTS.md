# Cursor / AI エージェント向け — exp_028

## 位置づけ

- **由来**: [exp_027](../exp_027_biped_ppo_walk/) をコピー（機能同一。以降の変更は本フォルダで行う）
- **ベース**: [exp_026](../exp_026_biped_ppo_hop_balance/)（MLP 256→256→128）
- **差分**: ホップ/すり足ではなく **交互片脚歩行** 向けの報酬・観測（`biped_walk_v1`、51 次元）
- **実行**: 本フォルダで `python train.py` / `python visualize.py`
- **レイアウト**: 本体は `sim/`（環境・報酬・観測）と `rl/`（PPO・ckpt）。補助は `scripts/`。ルートは `train.py` / `visualize.py` / `config.py` など入口のみ
- **コードリーディング**: 詳細手引きは [README.md](README.md) の「コードリーディングの手引き」（本 AGENTS.md には落とし穴のみ）
- **契約**: `contract.TELEMETRY_CONTRACT`（= `BIPED_WALK_V1`）
- **チェックポイント**: `mujoco_rl_sim/runs/exp_028_biped_ppo_walk/`

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

- 新 exp 派生時: [experiments/AGENTS.md](../AGENTS.md) の「新 exp 作成時 — README.md に書くこと」に従い README 手引きを更新（AGENTS へ長文手引きを複製しない）
- 観測次元を変える場合は `contract/biped_walk_v1.py` + `config.OBS_DIM` + `contract/validate`
- sweep に載せるキーは `lib/dispatch_config.SWEEPABLE_CONFIG_KEYS` に追加
- exp_026 のチェックポイントは **観測 48→51** のためそのまま読めない
- 飛翔中の IMU `dx` を主報酬に戻さない（exp_008 ホッパ主線と混同しない）
