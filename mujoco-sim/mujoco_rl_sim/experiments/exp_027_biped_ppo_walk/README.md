# exp_027: 交互片脚歩行 PPO（exp_026 ベース）

**exp_026** の MLP・学習ハイパラを維持し、タスクを **人間型の交互片脚歩行** に変更した実験です。

| 項目 | exp_026 | exp_027 |
|------|---------|---------|
| 前進報酬 | 飛翔中も IMU `dx`、両足 `foot_dx` 合算可 | **片足支持時のみ** |
| すり足 | 抑制なし | **`double_support_penalty`** |
| 位相 | push/landing 無効 | **push / landing / 交互着地 / 遊脚離地** |
| 観測 | 48 次元 `biped_ppo_v1` | **51 次元 `biped_walk_v1`** |

## 実行

```bash
cd exp_027_biped_ppo_walk
pip install -r requirements.txt
python train.py
python visualize.py
```

契約表: `python -m contract markdown`

## 報酬の要点

- `forward_imu` + `forward_foot`: `single_support` かつ `upright ≥ 0.62` のときのみ
- `double_support_penalty`: 両足接地中の前進（`dx` / 足 `dx`）に比例＋ベース
- `alternating_landing_bonus`: 反対脚支持からの着地エッジ
- `flight_duration_penalty`: 両足非接地が 4 step 超（ホップ抑制）
- `progress_bonus`: 片足支持時のみ IMU +X 最高値を更新

## 観測の追加（idx 12–14）

- 左/右足 site Z（正規化）
- 片足支持フラグ（+1 / それ以外 -1）

チェックポイント: `mujoco_rl_sim/runs/exp_027_biped_ppo_walk/`
