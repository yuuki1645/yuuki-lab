# Cursor / AI エージェント向け — exp_025

## 位置づけ

- **学習・報酬・観測は exp_024 と同一**（スタンドアロン化の fork）
- **外部パッケージ非依存**: `contract/` `lib/`（run_dir 等）`telemetry/` `mujoco_sim_common/` を本フォルダに同梱
- **実行**: 本フォルダで `python train.py` / `python visualize.py`（`_paths.install()` で sys.path を設定）
- **チェックポイント**: `runs/<フォルダ名>/`（実験ディレクトリ直下・CWD 非依存）

## 変更時の注意

- 姿勢量は `lib/pose.py` に集約（exp_024 と同じ）
- 観測次元を変える場合は `contract/biped_v1.py` + `contract/validate` を更新
- 他の `exp_*` や `mujoco_rl_sim` 本体への波及は意図しない（このフォルダ内だけで完結させる）
