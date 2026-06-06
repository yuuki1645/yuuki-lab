# exp_016: 生存延長（落下速度ペナルティ + 長ウォームアップ）

## 仮説

`imu_z` 早期終了は前傾ダイブの急落下が主因。非接地の急 `imu_dz` を罰し、前傾・摩擦・ウォームアップでホップ連鎖を延ばす。

## 変更（exp_010 比）

- `WARMUP_DURATION_S`: 1.2 → **2.0**
- 足底 `friction`: 1.15 → **1.28**（`model/main.xml`）
- **`IMU_FALL_PENALTY_SCALE=4.0`**（非接地・急落下、`IMU_FALL_PENALTY_DZ_THRESH=0.0015`）
- 前傾強化: `LEAN_FORWARD_PENALTY_SCALE` 6.0→**9.0**、`LEAN_FORWARD_THRESH` 0.14→**0.12**
- IMU 前進ゲート: `FORWARD_IMU_LEAN_GATE_THRESH` 0.10→**0.08**

## 学習

```bash
cd mujoco-sim/mujoco_rl_sim/experiments/exp_016_2joint_ppo_hop_survive
python train.py
```

チェックポイント: `mujoco_rl_sim/runs/exp_016_2joint_ppo_hop_survive/run_YYYYMMDD_HHMMSS/`

## 結果（seed 42）

| checkpoint | dx_pol | 備考 |
|------------|--------|------|
| （学習後に記入） | | |
