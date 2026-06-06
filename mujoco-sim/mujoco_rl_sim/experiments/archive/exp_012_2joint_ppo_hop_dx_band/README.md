# exp_012: ホップ速度帯 + 生存ボーナス（exp_011 u3500 微調整）

## 仮説

| 仮説 | 検証方法 |
|------|----------|
| exp_011 は u3500 以降ポリシーが崩れた | **u3500 から低 LR 再開** |
| ダイブ型の大きな dx だけでは 10 m に届かない | **飛翔中 dx 帯ボーナス** |
| 早期 `imu_z` 終了が距離を制限 | **生存ボーナス** |

転移: `../exp_011_2joint_ppo_hop_upright_vel/run_20260524_182506/update_003500.pt`

## 学習

```bash
python -m mujoco_rl_sim.experiments.archive.exp_012_2joint_ppo_hop_dx_band.train \
  --resume "../exp_011_2joint_ppo_hop_upright_vel/run_20260524_182506/update_003500.pt" \
  --lr 8e-5 --num-updates 1200
```
