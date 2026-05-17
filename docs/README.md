# ドキュメント一覧

強化学習・MuJoCo シミュレーション設計のための参照資料です。

| ファイル | 内容 |
|---------|------|
| [robot_spec.md](robot_spec.md) | 実機ロボット（カゴ・サーボ・バッテリー等）の寸法・重量 |
| [human_anthropometry.md](human_anthropometry.md) | 人間の身長・肢節長・質量・重心（典型値） |
| [human_joint_torque.md](human_joint_torque.md) | 関節トルク（等尺性最大・歩行ピーク・ロボットとの比較） |
| [human_joint_kinematics.md](human_joint_kinematics.md) | 可動域・歩行時の角度・角速度 |
| [sim_human_comparison.md](sim_human_comparison.md) | MuJoCo モデル（007 等）と人間・実機の対応表 |

## 使い方の目安

1. **報酬設計**（「人間らしい膝曲げ」など）→ `human_joint_kinematics.md` の歩行時角度と、シミュレーションの符号・軸を `sim_human_comparison.md` で照合する。
2. **質量・長さのチューニング** → `human_anthropometry.md` でオーダーを確認し、`robot_spec.md` / XML の `mass` を合わせる。
3. **アクチュエータ飽和** → `human_joint_torque.md` の歩行ピークと `forcerange`（例: ±14.7 N·m）を比較する。

数値は文献上の**典型値・代表例**です。個人差・速度・地面条件で大きく変わります。
