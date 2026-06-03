# exp_027 メモ

exp_026 からの差分: **交互片脚歩行**向け報酬・観測（ホップ/すり足抑制）。

| 項目 | exp_026 | exp_027 |
|------|---------|---------|
| タスク | ホップ主線 + すり足許容 | **片足支持時のみ前進** |
| 観測 | 48 次元 `biped_ppo_v1` | **51 次元 `biped_walk_v1`** |
| 前進 | 飛翔中も IMU dx | **片足支持時のみ** |
| すり足 | 両足合算 foot_dx 可 | **`double_support_penalty`** |
| 位相 | push/landing 無効 | **push / landing / 交互着地** |

## sweep

- 本線: `walk_reward_sweep_48.yaml`（歩行報酬 3 軸 × 4 seed = 48）
- LR スイープは廃止（歩行タスクでは shaping 係数の方が感度大）

## 学習結果の考察

（未記入）
