# 04 — 時間差分（TD）学習

## モンテカルロ vs TD

| 方式 | return の見積もり | 特徴 |
|------|------------------|------|
| **モンテカルロ** | エピソード終了まで実際の報酬を足す | 不偏だが分散が大きい |
| **TD** | $r + \gamma V(s')$ で途中から見積もる | 分散が小さいがバイアスあり（bootstrapping） |

深層 RL では **TD 系が主流** です。PPO の advantage 計算も TD の延長上にあります。

## TD error

$$
\delta_t = r_t + \gamma V(s_{t+1}) - V(s_t)
$$

- $\delta_t > 0$ … 想定より良かった → その行動を強化したい  
- $\delta_t < 0$ … 想定より悪かった → 弱化したい  

これが critic 学習の学習信号になります。

## bootstrapping

エピソードが終わる前に $V(s')$ で「続き」を見積もることです。

| 終了 | $V(s')$ の扱い |
|------|------------------|
| 通常ステップ | $V(s_{t+1})$ を使う |
| **terminated** | 0（これ以上報酬なし） |
| **truncated** | $V(s_{t+1})$ を使う（続きがありうる） |

Gymnasium の `terminated` / `truncated` 分離はここに直結します → [practice/termination-and-truncation.md](../practice/termination-and-truncation.md)

## GAE（PPO で使用）

**Generalized Advantage Estimation** は、複数ステップの TD error を $\lambda$ で重み付け平均したものです。

- $\lambda = 0$ … 1 ステップ TD に近い（低分散・高バイアス）
- $\lambda = 1$ … モンテカルロに近い（高分散・低バイアス）

exp_030 既定: `gae_lambda: 0.95`（`conf/ppo/default.yaml`）

詳細は [algorithms/ppo.md](../algorithms/ppo.md)

## bias-variance の実務的意味

| 症状 | 可能性 |
|------|--------|
| 学習が不安定・激しく振動 | advantage の分散が大きい → $\lambda$ を下げる、batch を増やす |
| 学習が遅い・局所最適にハマる | バイアスが大きい → rollout を長く、$\gamma$ を確認 |

## 次に読む

- [algorithms/ppo.md](../algorithms/ppo.md)
- [05-exploration.md](05-exploration.md)
