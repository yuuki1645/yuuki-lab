# Actor-Critic

**Actor**（方策）と **Critic**（価値）を同時に学習する枠組みです。

## 2 つのネットワーク

```text
観測 s ──→ Actor  ──→ 行動 a ~ π(a|s)
     │
     └──→ Critic ──→ V(s) または Q(s,a)
```

| 役割 | 学習内容 |
|------|---------|
| Actor | より高い return が得られる行動を選ぶ |
| Critic | 状態の「良さ」を予測し、actor の学習信号（advantage）を提供 |

exp_030 では actor / critic とも MLP 256→256→128 です（`conf/sim/default.yaml`）。

## Advantage の役割

\[
A_t \approx Q(s_t, a_t) - V(s_t)
\]

「この行動は、その状態での平均よりどれだけ良かったか」を表します。

- \(A_t > 0\) … この行動を強化  
- \(A_t < 0\) … この行動を弱化  

PPO では GAE で \(A_t\) を推定します → [ppo.md](ppo.md)

## Critic 損失

TD 目標に近づける回帰損失が一般的です。

\[
L_\text{value} = (V(s_t) - G_t^\text{target})^2
\]

exp_030 では `value_coef: 0.5` で actor 損失とのバランスを取ります。

## A2C / A3C との関係

同期的に actor と critic を更新するのが **A2C**、非同期並列が **A3C** です。  
PPO は A2C 系の延長で、**複数 epoch の再利用 + clip** が加わったものと捉えられます。

→ [a2c-a3c.md](a2c-a3c.md)

## よくある問題

| 症状 | 可能性 |
|------|--------|
| critic loss だけ下がる | 価値は当てられるが方策が改善しない → 報酬設計を疑う |
| actor と critic で学習率のバランス | `lr` 共通だが `value_coef` で調整 |
| advantage が常に正 | baseline が低い / 報酬スケールが偏っている |

## 次に読む

- [ppo.md](ppo.md)
- [practice/hyperparameters.md](../practice/hyperparameters.md)
