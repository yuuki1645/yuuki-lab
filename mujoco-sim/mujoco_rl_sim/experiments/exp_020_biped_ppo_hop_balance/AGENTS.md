# Cursor / AI エージェント向け — exp_020

## 位置づけ

- **学習・報酬・観測は exp_019 と同一**（`config`・`env`・`reward` は 019 からコピー）
- **契約**: `mujoco_rl_sim.contract` の `BIPED_PPO_V1`（`experiment_contract.py`）
- **train**: `contract.session.run_ppo_train`（`train.py` は薄いエントリ）
- **比較ベースライン**: exp_019

## 変更時の注意

- 観測次元・テレメトリキーを変えるときは **`mujoco_rl_sim/contract/biped_v1.py`** を更新し、`python -m mujoco_rl_sim.contract validate` を通す
- Hub の型は `trainingTelemetry.ts`（`biped_ppo_v1`）を契約と同期
- exp_019 だけ直して 020 と乖離させない（契約は共有）
