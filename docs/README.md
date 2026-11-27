# ドキュメント一覧

実機の制御、強化学習、シミュレーション設計の参照資料です。  
**いまの方針は [now.md](now.md)** です。  
**RL 本線は [Isaac Lab](../isaac-lab/README.md)** の `YuukiLab-BipedWalk-v0` です。  
**機体の制御の基本は [robot_control.md](robot_control.md)** です。  
**関節角の正本は [joint_angles.md](joint_angles.md)** です。

| ファイル | 内容 |
|---------|------|
| [now.md](now.md) | **いまの方針**（Fusion の歩行学習、箱モデルと MuJoCo の位置づけ、Hub のポート） |
| [sim_to_real.md](sim_to_real.md) | **実機とシミュの交互**（直立から始める。自由歩行の前に見る量） |
| [joint_angles.md](joint_angles.md) | **関節角の正本**（中立、プラスの向き、実機の窓と仮の範囲） |
| [robot_control.md](robot_control.md) | **実機の制御**（CoreS3、両脚の ATOM S3R、CAN、サブ PC、タブレット） |
| [heel_teleop.md](heel_teleop.md) | **ゲームパッドで踵を動かす**（Isaac の起動、Hub への出し方、実機の起動と操作） |
| [rl/](rl/README.md) | **強化学習の汎用解説**（基礎・PPO 等・実務・学び直し） |
| [experiments/](experiments/README.md) | **強化学習実験の詳細解説**（参照: MuJoCo exp_030。Isaac の現行仕様は isaac-lab） |
| [prometheus.md](prometheus.md) | **プロメテウス（レガシー）** — 自宅 LAN 分散強化学習（旧 `dispatch`） |
| [../aws/README.md](../aws/README.md) | **AWS 並列学習（MuJoCo exp_030 向け・レガシー）** — `aws_launch.py`・EC2 Spot・S3 |
| [robot_spec.md](robot_spec.md) | 実機ロボット（カゴ・サーボ・バッテリー等）の寸法・重量 |
| [human_anthropometry.md](human_anthropometry.md) | 人間の身長・肢節長・質量・重心（典型値） |
| [human_joint_torque.md](human_joint_torque.md) | 関節トルク（等尺性最大・歩行ピーク・ロボットとの比較） |
| [human_joint_kinematics.md](human_joint_kinematics.md) | 可動域・歩行時の角度・角速度 |
| [sim_human_comparison.md](sim_human_comparison.md) | MuJoCo モデル（007 等）と人間・実機の対応表 |
| [control_timing_human_rl.md](control_timing_human_rl.md) | 人体の制御タイミング（ms / Hz）と RL 環境 step 周波数の目安 |
| [../mujoco-sim/mujoco_rl_sim/experiments/archive/exp_001_2joint_a2c/README.md](../mujoco-sim/mujoco_rl_sim/experiments/archive/exp_001_2joint_a2c/README.md) | exp_001: 2 関節 A2C 実験（アーカイブ） |
| [../mujoco-sim/mujoco_rl_sim/experiments/archive/exp_002_2joint_a2c/README.md](../mujoco-sim/mujoco_rl_sim/experiments/archive/exp_002_2joint_a2c/README.md) | exp_002: 2 関節 A2C 実験（アーカイブ・exp_001 コピー） |

## 使い方の目安

1. **関節の中立とプラスの向き** → [joint_angles.md](joint_angles.md)。
2. **実機とシミュを交互に見る** → [sim_to_real.md](sim_to_real.md)。最初は直立。
3. **機体の制御を確認する** → [robot_control.md](robot_control.md)。パッドで踵を動かす手順は [heel_teleop.md](heel_teleop.md)。
4. **いま学習を回す** → [../isaac-lab/README.md](../isaac-lab/README.md)。
5. **強化学習の基礎・PPO の復習** → [rl/README.md](rl/README.md)（学び直しは [rl/yuuki-lab/sutton-barto-map.md](rl/yuuki-lab/sutton-barto-map.md) から）。
6. **報酬設計**（「人間らしい膝曲げ」など）→ `human_joint_kinematics.md` の歩行時角度と、シミュレーションの符号・軸を `sim_human_comparison.md` で照合する。実機のプラスの向きは [joint_angles.md](joint_angles.md)。
7. **質量・長さのチューニング** → `human_anthropometry.md` でオーダーを確認し、`robot_spec.md` / XML の `mass` を合わせる。
8. **アクチュエータ飽和** → `human_joint_torque.md` の歩行ピークと `forcerange`（例: ±14.7 N·m）を比較する。
9. **制御周期・環境 step の Hz** → `control_timing_human_rl.md` で人体のフィードバック周波数と RL の推奨帯（50〜100 Hz 等）を確認する。

人間の寸法・トルク・歩行角度は文献上の**典型値・代表例**です。個人差・速度・地面条件で大きく変わります。関節角の中立とプラスの向きは [joint_angles.md](joint_angles.md) が実機の規定です。
