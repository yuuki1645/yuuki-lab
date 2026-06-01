# Cursor / AI エージェント向け — exp_008

## 絶対に誤解しないこと

1. **この実験は両脚歩行（バイペッド）ではない。**
2. **「2joint」= 脚が 2 本ではなく、膝 + 足首の 2 関節。**
3. **ロボットは片脚（モノポッド）1 本 + `freejoint`。**
4. **タスクはホッピング。** 常時足底接地を前提にした歩行報酬は不適切（`exp_007a` は参考 ablation のみ）。

## 報酬設計の意図

- **飛翔中の IMU `dx` 前進** … ホップの主報酬（維持）
- **`foot_dx` 前進** … 足底接地時のみ（立脚押し出し）
- **前傾ペナルティ** … 長い非接地 + 強い前傾（前倒れダイブ抑制）
- **`contact_shank`** … 即終了しない（学習継続のためペナルティ）
- **膝屈曲の常時ボーナス** … 使わない（歩行スタンス向けだった）

## 変更時の禁止・注意

| やらないこと | 理由 |
|--------------|------|
| `FORWARD_REQUIRE_FOOT_CONTACT=True` を主線にする | 飛翔前進を殺す |
| 飛翔中の IMU `dx` をゼロ化 | ホッパのタスク定義と矛盾 |
| 「両脚」「歩行周期」「左右脚」前提の shaping を追加 | モデルに存在しない |
| `KNEE_HUMAN_FLEX` 常時ボーナスを復活 | 前傾＋曲げ膝ハックを助長 |

## ファイルの責務

- `config.py` … 係数・`ROBOT_MORPHOLOGY`
- `reward.py` … 位相ゲート付き shaping
- `termination.py` … shank はペナルティのみ
- `episode_state.py` … 着地エッジ・`flight_steps`
- `env.py` … shank ペナルティ集計

## 評価

`analyze_rollout --seed 42` 固定で exp_006 と比較。  
wandb: `episode/landing_count`, `episode/max_flight_steps`, `episode/shank_step_penalty_sum`
