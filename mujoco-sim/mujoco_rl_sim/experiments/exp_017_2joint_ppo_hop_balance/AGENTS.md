# Cursor / AI エージェント向け — exp_009

exp_008 の AGENTS.md を継承。追加の意図:

- **飛翔 IMU `dx` は維持**するが、強い前傾（`imu_zaxis_x` 大）では **係数を下げる**（ゼロ化しない）
- **長い非接地**には `flight_duration_penalty`（着地を促す）
- **評価エピソードは 30 s** — `total_dx_policy` で 10 m 前進を確認

## 変更時の注意

| やらないこと | 理由 |
|--------------|------|
| 飛翔中の IMU `dx` を完全ゼロ化 | ホッパ定義と矛盾 |
| `FORWARD_REQUIRE_FOOT_CONTACT=True` を主線にする | exp_007a 系 ablation のみ |
