# exp_015: ホップ周期完了ボーナス

## 仮説

1 回の大きな前傾ダイブより、**離地→着地で一定以上前進したホップを繰り返す**方が 10 m に到達しやすい。

## 変更（exp_010 比）

- 着地時: `flight_steps >= 5` かつ周期 `dx >= 0.06 m` かつ直立・前傾制限 → `+4.0`（`HOP_CYCLE_BONUS`）
- 観測・終了・XML は exp_010 と同一

## 転移

```powershell
cd mujoco-sim
python -m mujoco_rl_sim.experiments.exp_015_2joint_ppo_hop_cycle.train `
  --resume "../exp_010_2joint_ppo_hop_progress/run_20260524_173035/final.pt" `
  --lr 1e-4 --num-updates 2000
```

## 結果（seed 42, analyze_rollout）

| checkpoint | dx_pol | 備考 |
|------------|--------|------|
| （学習後に記入） | | |
