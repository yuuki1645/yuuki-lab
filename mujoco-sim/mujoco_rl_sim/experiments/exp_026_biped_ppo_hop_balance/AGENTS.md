# Cursor / AI エージェント向け — exp_026

## 位置づけ

- **学習・報酬・観測・モデル XML は [exp_025](../exp_025_biped_ppo_hop_balance/) と同一**
- **差分**: 方策 / Critic MLP を `config.POLICY_HIDDEN_SIZES = (256, 256, 128)` に拡大（exp_025 は 64→64）
- **外部パッケージ非依存**: `contract/` `lib/` `telemetry/` `mujoco_sim_common/` を本フォルダに同梱
- **実行**: 本フォルダで `python train.py` / `python visualize.py`
- **チェックポイント**: `mujoco_rl_sim/runs/<フォルダ名>/`（CWD 非依存）

## 変更時の注意

- ネットワーク幅を変えるときは `config.POLICY_HIDDEN_SIZES` と `agent._build_mlp` の整合を保つ
- exp_025 のチェックポイントは層形状が異なるため **そのまま読み込めない**
- 観測次元を変える場合は `contract/biped_v1.py` + `contract/validate` を更新
