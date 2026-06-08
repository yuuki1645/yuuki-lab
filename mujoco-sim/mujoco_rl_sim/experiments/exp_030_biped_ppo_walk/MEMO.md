# exp_030 メモ

exp_029 をコピーした runs 整理用 fork（2026-06）。**コピー時点でコードは exp_029 と同一**。

## 目的

- `runs/exp_029_biped_ppo_walk/` の run 名混在（日付 / wandb 名）を切り離す
- 以降の本線学習・eval・`eval_compare` は **exp_030 の runs のみ** で管理

## タスク差分（exp_026 比・027/028/029/030 共通）

| 項目 | exp_026 | exp_030 |
|------|---------|---------|
| タスク | ホップ主線 + すり足許容 | **片足支持時のみ前進** |
| 観測 | 48 次元 `biped_ppo_v1` | **51 次元 `biped_walk_v1`** |
| 前進 | 飛翔中も IMU dx | **片足支持時のみ** |
| すり足 | 両足合算 foot_dx 可 | **`double_support_penalty`** |
| 位相 | push/landing 無効 | **push / landing / 交互着地** |

## sweep

- 本線: `walk_reward_sweep_48.yaml`（歩行報酬 3 軸 × 4 seed = 48）
- スモーク: `baseline_10seed.yaml`（10 seed）
- sweep_id プレフィックスは `exp030_*`（exp_029 と衝突しない）

## 学習結果の考察

（未記入）
