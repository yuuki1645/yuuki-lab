# 方策勾配（Policy Gradient）

方策 $\pi_\theta(a|s)$ のパラメータ $\theta$ を、**勾配上昇** で直接最適化する手法群の総称です。

## 基本アイデア

目標 $J(\theta) = \mathbb{E}_\pi[G_0]$ を最大化するため、

$$
\nabla_\theta J(\theta) \propto \mathbb{E}\left[ \nabla_\theta \log \pi_\theta(a|s) \cdot G_t \right]
$$

「良い軌道（$G_t$ が大きい）で取った行動の確率を上げる」という直感です。

## REINFORCE

モンテカルロで $G_t$ をそのまま使う最も素朴な方策勾配法です。

| 長所 | 短所 |
|------|------|
| 実装が単純 | 分散が非常に大きい |
| 方策を直接学習 | サンプル効率が悪い |

## 分散を下げる: baseline

$G_t$ の代わりに **advantage** $A_t = G_t - b(s_t)$ を使います。  
$b(s_t) = V(s_t)$（critic）が一般的です。

$$
\nabla_\theta J \propto \mathbb{E}\left[ \nabla_\theta \log \pi_\theta(a|s) \cdot A_t \right]
$$

→ [actor-critic.md](actor-critic.md)

## ログ確率 $\log \pi_\theta(a|s)$

連続ガウス方策では、選んだ行動の対数確率が解析的に計算できます。  
PPO の損失はこの $\log \pi$ の差分（重要度比）を使います。

## on-policy である理由

方策勾配の期待値は **現在の方策でサンプルした軌道** について取ります。  
方策が大きく変わると、古いデータの勾配は信頼できなくなります。

## 現代の方策勾配

| 手法 | 特徴 |
|------|------|
| TRPO | 信頼領域で KL 制約 |
| **PPO** | clip で簡易に同様の効果（**yuuki-lab 本線**） |

## 次に読む

- [actor-critic.md](actor-critic.md)
- [ppo.md](ppo.md)
- [foundations/03-policy-and-value.md](../foundations/03-policy-and-value.md)
