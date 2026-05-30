# Cursor / AI エージェント向け — exp_023

## 位置づけ

- **exp_021 のコピー**（学習・報酬・観測・契約は同一）
- **モデル差分**: `model/main.xml` の足裏アルミ板
  - **Y 幅 17 cm → 10 cm**（`size` の Y 半長 `0.085` → `0.05`）
  - **中心 X を -2.5 cm**（`pos` X `0.125` → `0.10`、踵側が sole 原点より 2.5 cm 後方にはみ出す）
- **契約**: `mujoco_rl_sim.contract` の `BIPED_PPO_V1`（`experiment_contract.py`）
- **比較ベースライン**: exp_021

## 変更時の注意

- 足裏寸法を変えるときは `main.xml` の `size`（半長）、`pos`（中心）、`foot_site` / `heel_bottom_site` / `toe_bottom_site` を整合させる
- 観測次元・テレメトリキーは exp_021 と同じ（契約変更時は `biped_v1.py` + `validate`）
