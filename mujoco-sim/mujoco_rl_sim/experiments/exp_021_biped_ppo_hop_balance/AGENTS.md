# Cursor / AI エージェント向け — exp_021

## 位置づけ

- **exp_020 のコピー**（学習・報酬・観測・契約は同一）
- **モデル差分**: `model/main.xml` の足裏アルミ板 **30 cm → 25 cm**（+X 方向、`foot_plate` / `right_foot_plate`）
- **契約**: `mujoco_rl_sim.contract` の `BIPED_PPO_V1`（`experiment_contract.py`）
- **比較ベースライン**: exp_020

## 変更時の注意

- 足裏寸法を変えるときは `main.xml` の `size`（半長）、`pos`（中心）、`foot_site` / `toe_bottom_site` を整合させる
- 観測次元・テレメトリキーは exp_020 と同じ（契約変更時は `biped_v1.py` + `validate`）
