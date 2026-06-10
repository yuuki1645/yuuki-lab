# 03 — 方策と価値関数

## 方策 $\pi(a|s)$

状態 $s$ で **どの行動を取るか** のルールです。

| 種類 | 記法 | 例 |
|------|------|-----|
| 確定的 | $a = \pi(s)$ | 平均トルクをそのまま出力 |
| 確率的 | $a \sim \pi(\cdot|s)$ | ガウス分布からサンプル（exp_030 の PPO） |

PPO では連続行動空間で **ガウス方策**（平均 + 学習可能な標準偏差）を使います。

## 価値関数 $V^\pi(s)$

「状態 $s$ から方策 $\pi$ に従ったとき、将来どれだけ報酬が取れるか」の期待値です。

$$
V^\pi(s) = \mathbb{E}_\pi[G_t \mid s_t = s]
$$

**critic** ネットワークがこれを近似します。

## 行動価値 $Q^\pi(s,a)$

「状態 $s$ で行動 $a$ を取り、その後 $\pi$ に従ったとき」の期待 return です。

$$
Q^\pi(s,a) = \mathbb{E}_\pi[G_t \mid s_t=s, a_t=a]
$$

Actor-Critic では advantage を $Q - V$ で表すことが多いです。

## ベルマン方程式（直感）

現在の価値は「即時報酬 + 割引された次の価値」で書けます。

$$
V^\pi(s) = \mathbb{E}_{a,s'} \left[ r + \gamma V^\pi(s') \right]
$$

TD 学習は、この式の **ずれ（TD error）** を小さくする方向に学習します。

## 方策ベース vs 価値ベース

| 方式 | 学ぶもの | 代表 algo |
|------|---------|-----------|
| 価値ベース | $Q(s,a)$ から行動を間接的に選ぶ | DQN |
| 方策ベース | $\pi(a|s)$ を直接最適化 | REINFORCE, PPO |
| Actor-Critic | 両方 | A2C, PPO |

連続制御のロボット歩行では **方策勾配系（PPO）** が一般的です。

## 最適方策 $\pi^*$

どの状態でも期待 return が最大になる方策です。  
RL の目標は $\pi_\theta \approx \pi^*$ を見つけることですが、**報酬設計が違えば $\pi^*$ も変わります**。

## 次に読む

- [04-temporal-difference.md](04-temporal-difference.md)
- [algorithms/actor-critic.md](../algorithms/actor-critic.md)
