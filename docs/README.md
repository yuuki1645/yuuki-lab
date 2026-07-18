# ドキュメント一覧

強化学習・シミュレーション設計のための参照資料です。  
**RL 本線は [Isaac Lab](../isaac-lab/README.md)**（実験 docs: [experiments/isaac_biped_ppo_walk](experiments/isaac_biped_ppo_walk/README.md)）。

| ファイル | 内容 |
|---------|------|
| [rl/](rl/README.md) | **強化学習の汎用解説**（基礎・PPO 等・実務・学び直し） |
| [experiments/](experiments/README.md) | **強化学習実験の詳細解説**（本線: Isaac / 参照: MuJoCo exp_030） |
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

1. **いま学習を回す** → [../isaac-lab/README.md](../isaac-lab/README.md) と [experiments/isaac_biped_ppo_walk](experiments/isaac_biped_ppo_walk/README.md)。
2. **強化学習の基礎・PPO の復習** → [rl/README.md](rl/README.md)（学び直しは [rl/yuuki-lab/sutton-barto-map.md](rl/yuuki-lab/sutton-barto-map.md) から）。
3. **報酬設計**（「人間らしい膝曲げ」など）→ `human_joint_kinematics.md` の歩行時角度と、シミュレーションの符号・軸を `sim_human_comparison.md` で照合する。
4. **質量・長さのチューニング** → `human_anthropometry.md` でオーダーを確認し、`robot_spec.md` / XML の `mass` を合わせる。
5. **アクチュエータ飽和** → `human_joint_torque.md` の歩行ピークと `forcerange`（例: ±14.7 N·m）を比較する。
6. **制御周期・環境 step の Hz** → `control_timing_human_rl.md` で人体のフィードバック周波数と RL の推奨帯（50〜100 Hz 等）を確認する。

数値は文献上の**典型値・代表例**です。個人差・速度・地面条件で大きく変わります。
