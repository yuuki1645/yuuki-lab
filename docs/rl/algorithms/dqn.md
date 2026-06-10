# DQN（Deep Q-Network）

**価値ベース** の深層 RL です。$Q(s,a)$ をニューラルネットで近似し、$\epsilon$-greedy で行動を選びます。

## 概要

| 項目 | 内容 |
|------|------|
| 学習対象 | $Q_\theta(s,a)$ |
| 行動選択 | $\arg\max_a Q(s,a)$（探索時はランダム） |
| データ効率 | **off-policy**（リプレイバッファで古いデータを再利用） |
| 行動空間 | **離散** が前提 |

## yuuki-lab との関係

本線の歩行実験は **連続トルク制御** のため DQN は使っていません。  
archive の離散化実験や、「価値ベース vs 方策ベース」の対比理解用です。

## PPO との対比

| | DQN | PPO |
|---|-----|-----|
| 方策 | 間接的（Q から導出） | 直接 $\pi(a|s)$ |
| on/off | off-policy | on-policy |
| 連続制御 | 離散化が必要 | ネイティブ対応 |
| ロボット歩行 | あまり使わない | **標準** |

## 代表的な工夫

- **Experience replay** … 過去の遷移をランダムサンプル  
- **Target network** … Q の更新目標を安定化  
- **Double DQN** … 過大評価の抑制  

## 次に読む

- [policy-gradient.md](policy-gradient.md)
- [ppo.md](ppo.md)
