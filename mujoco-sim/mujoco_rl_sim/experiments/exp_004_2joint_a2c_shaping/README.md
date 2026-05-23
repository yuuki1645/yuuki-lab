# exp_004: 2 関節脚 A2C + reward shaping

`exp_003_2joint_a2c` をベースに、`exp_001_2joint_a2c` の **reward shaping** と **姿勢ベース早期終了** を追加した実験。

## exp_003 との主な差分

| 項目 | exp_003 | exp_004 |
|------|---------|---------|
| 毎ステップ shaping | なし | 直立・膝・後傾・低姿勢 |
| 前進 `FORWARD_MIN_UPRIGHT` | 0.72 | **0.65**（到達可能域に緩和） |
| 早期終了 | 接触のみ | **姿勢 + 接触** |
| 膝ボーナス | — | 直立度ゲート付き（倒れハック抑制） |

## 学習

`mujoco-sim` ディレクトリで:

```bash
python -m mujoco_rl_sim.experiments.exp_004_2joint_a2c_shaping.train
```

チェックポイント: `mujoco_rl_sim/runs/exp_004_2joint_a2c_shaping/run_YYYYMMDD_HHMMSS/`

## wandb で見る指標（shaping）

- `episode/shaping_sum`
- `episode/upright_bonus_sum`
- `episode/backward_lean_penalty_sum` / `episode/height_penalty_sum`
- `termination/rate_imu_z` など姿勢終了率

## 関連

- [exp_003 README](../exp_003_2joint_a2c/README.md)
- [exp_001 reward.py](../exp_001_2joint_a2c/reward.py)（shaping の参照元）
