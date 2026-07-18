# A2C / A3C

**Advantage Actor-Critic** の同期版（A2C）と非同期版（A3C）です。

## 概要

| 版 | 特徴 |
|----|------|
| **A3C** | 複数ワーカーが非同期に環境を回し、勾配を共有 |
| **A2C** | 同期版。実装が単純で再現性が高い |

方策と価値を同時に学習する点は PPO と同系統です。  
PPO は「同じ rollout を clip 付きで複数 epoch 使う」点が異なります。

## yuuki-lab での位置づけ

| 実験 | algo | 状態 |
|------|------|------|
| archive exp_001, exp_002 | A2C | アーカイブ（片脚 2 関節） |
| exp_030（MuJoCo） | PPO | 参照（旧本線） |
| Isaac Lab biped_ppo_walk | PPO（RSL-RL） | **本線** |

アーカイブ README: [exp_001](../../../mujoco-sim/mujoco_rl_sim/experiments/archive/exp_001_2joint_a2c/README.md)

## A2C から PPO へ移行した理由（一般的）

| 観点 | A2C | PPO |
|------|-----|-----|
| 更新の安定性 | やや不安定になりうる | clip で安定 |
| サンプル効率 | 1 回のデータで 1 回更新が基本 | 複数 epoch 再利用 |
| 連続制御ロボット | 使われる | **より広く使われる** |

yuuki-lab では exp_015 以降バイペッド系に移行し、MuJoCo では exp_030（Hydra + PPO + VecEnv）まで進めたあと、**学習本線を Isaac Lab（RSL-RL PPO）へ移しました**。

## 次に読む

- [ppo.md](ppo.md)
- [actor-critic.md](actor-critic.md)
