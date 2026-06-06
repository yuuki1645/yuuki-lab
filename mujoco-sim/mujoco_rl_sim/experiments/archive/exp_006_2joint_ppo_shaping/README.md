# exp_006: 2 関節脚 PPO + 足底幾何観測（exp_005 比較用）

> **ロボット形態**: 片脚モノポッド 1 本（`freejoint`）。「2joint」= 膝・足首 2 自由度で、**両脚ではない**。  
> ホッパ向け shaping は **[exp_008](../exp_008_2joint_ppo_hop_shaping/README.md)** を参照。

`exp_005_2joint_ppo_shaping` をベースに、**観測のみ**拡張した実験。
報酬・終了・PPO ハイパーパラメータ・制御レート（50 Hz）は exp_005 と同一。

## exp_005 との差分（観測・モデル site）

| 項目 | exp_005 | exp_006 |
|------|---------|---------|
| `obs_dim` | 19 | **25** |
| 足底 site | `foot_site`（板中心）, `toe_site`（板外） | `foot_site`, **`heel_bottom_site`**, **`toe_bottom_site`**（板 X± 端・底面 z=-0.01） |
| 追加観測 | — | `toe_z`, `heel_z`, `knee_heel_dx/dz`, `imu_heel_dx/dz` |

### PolicyObs の追加フィールド（正規化後）

- `toe_z`, `heel_z` … `height_to_norm`（`foot_z` と同スケール）
- `knee_heel_dx`, `knee_heel_dz` … 膝 joint anchor − `heel_bottom_site`（`clip_scale`, ±`MAX_REL_HEEL_OFFSET`）
- `imu_heel_dx`, `imu_heel_dz` … `imu_site` − `heel_bottom_site`（同上）

`com_x` の趾基準は `toe_bottom_site` の `toe_pos` センサに合わせた。

## 学習

`mujoco-sim` ディレクトリで:

```bash
python -m mujoco_rl_sim.experiments.archive.exp_006_2joint_ppo_shaping.train
```

チェックポイント: `mujoco_rl_sim/runs/archive/exp_006_2joint_ppo_shaping/run_YYYYMMDD_HHMMSS/`

**注意**: `obs_dim=19` の exp_005 チェックポイントはそのまま読み込めない。

## 可視化

```bash
python -m mujoco_rl_sim.experiments.archive.exp_006_2joint_ppo_shaping.visualize \
  --checkpoint run_YYYYMMDD_HHMMSS/final.pt
```

## 関連

- [exp_008 片脚ホッパ shaping](../exp_008_2joint_ppo_hop_shaping/README.md)
- [exp_005 README](../exp_005_2joint_ppo_shaping/README.md)
- [exp_004 README](../exp_004_2joint_a2c_shaping/README.md)
- [experiments 共通 AGENTS.md](../../AGENTS.md)
