# 観測設計と正規化

エージェントが見るのは **真の状態全体ではなく観測ベクトル** です。設計ミスは PPO 以前に学習を壊します。

## 何を入れるか

| カテゴリ | 例（歩行） |
|---------|-----------|
| 本体 | 関節角・角速度 |
| 慣性 | IMU（姿勢・加速度） |
| 接触 | 足の接地フラグ・力の代理 |
| 位相 | 片足支持・遊脚（内部状態の観測化） |

exp_030 は 51 次元 `biped_walk_v1`。idx 表は `python -m contract markdown` が正本。

## 正規化

| 手法 | 目的 |
|------|------|
| スケーリング | 各次元を似たオーダーに（勾配安定） |
| クリップ | 外れ値でネットが飽和するのを防ぐ |
| 相対座標 | 世界座標の絶対値より、タスクに必要な差分 |

実装: `sim/observation.py`

## マルコフ性との関係

観測だけではマルコフでない場合（例: 速度が観測に無い）、方策は過去を暗黙に記憶できず性能が落ちます。  
必要なら **履歴スタック** や **RNN** を検討しますが、exp_030 は MLP + 十分な即時観測で構成しています。

## 次元変更時の注意

観測次元を変えると **古いチェックポイントは読めません**。

1. `contract/biped_walk_v1.py`  
2. `conf/sim/default.yaml` の `obs_dim`  
3. `python -m contract validate`  
4. docs の [observation.md](../../experiments/exp_030_biped_ppo_walk/observation.md)

## 次に読む

- [foundations/06-function-approximation.md](../foundations/06-function-approximation.md)
- [human_joint_kinematics.md](../../human_joint_kinematics.md)
