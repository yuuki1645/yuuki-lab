# Cursor / AI エージェント向け — exp_017

exp_008 / exp_010 の AGENTS.md を継承。exp_017 の追加意図:

- **新しい shaping 項・終了緩和・XML 変更は入れない** — exp_011〜016 で u3500 以降の悪化が多かったため
- **既存報酬の重みだけ調整** — ステップ前進（`FORWARD_REWARD_SCALE`）↓、進捗・押し出し・着地↑
- 転移元は **exp_010 final**（~3.11 m が現状ベスト）。ベースライン比較も exp_010 final を基準にする
- **飛翔 IMU `dx` は維持**（前傾で減衰のみ、ゼロ化しない）
- **評価エピソードは 30 s** — `total_dx_policy` で 10 m 前進を確認

## exp_010 から変えた係数（config.py）

| 係数 | exp_010 | exp_017 |
|------|---------|---------|
| `FORWARD_REWARD_SCALE` | 80 | 55 |
| `PROGRESS_REWARD_SCALE` | 12 | 18 |
| `PUSH_OFF_BONUS_SCALE` | 0.25 | 0.45 |
| `LANDING_BONUS_SCALE` | 0.55 | 0.75 |
| `KNEE_HYPERFLEX_PENALTY_SCALE` | 2.5 | 3.2 |

観測・終了・XML は exp_010 と同一。

## 変更時の注意

| やらないこと | 理由 |
|--------------|------|
| 飛翔中の IMU `dx` を完全ゼロ化 | ホッパ定義と矛盾 |
| `FORWARD_REQUIRE_FOOT_CONTACT=True` を主線にする | exp_007a 系 ablation のみ |
| 新しい報酬項・終了緩和・摩擦変更を足す | exp_017 の仮説（重み調整のみ）と矛盾 |
| exp_010 final より悪化した ckpt を採用 | 現状ベストを下回る |

## 評価

`analyze_rollout --seed 42`（30 s）。u500 / u1000 / u2000 で exp_010 final（~3.1 m）と比較し、悪化なら打ち切り。
