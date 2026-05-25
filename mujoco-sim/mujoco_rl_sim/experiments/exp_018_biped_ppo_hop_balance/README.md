# exp_018: 両脚バイペッド前進 PPO（10 DOF）

## 概要

**両脚・全 10 サーボ**を最初から操作し、**+X 前進**を学習する PPO 実験。

- **観測 42 次元**: IMU（dx, gyro, zaxis, 高さ）+ 左右足接地・足元 dx + 10 関節 q/qvel + 直前 action
- **行動 10 次元**: `left/right` ×（hip_roll, hip_pitch, knee_pitch, ankle_pitch, ankle_roll）
- **報酬**: IMU/足元前進・進捗・直立・前後傾ペナルティ・遊脚（両足非接地）継続ペナルティ・膝過屈曲など（ホップ特化の push_off/landing は無効）
- **`model/main.xml`**: `docs/robot_spec.md` 準拠の両脚モデル

## 学習

```bash
cd mujoco-sim
python -m mujoco_rl_sim.experiments.exp_018_biped_ppo_hop_balance.train
```

## 可視化

```bash
# XML のみ（keyframe stand）
python -m mujoco_rl_sim.experiments.exp_018_biped_ppo_hop_balance.visualize

# 学習済みチェックポイント
python -m mujoco_rl_sim.experiments.exp_018_biped_ppo_hop_balance.visualize --checkpoint runs/.../latest.pt
```

## exp_017 との違い

| 項目 | exp_017 | exp_018 |
|------|---------|---------|
| 形態 | 片脚ホッパ | 両脚バイペッド |
| 操作 DOF | 2（膝・足首） | **10（全サーボ）** |
| 観測 | 25 | **42** |
| タスク | ホッピング | **+X 前進歩行** |
| ckpt 転用 | — | **不可**（次元不一致） |

## 結果

| checkpoint | 備考 |
|------------|------|
| （学習後に記入） | |
