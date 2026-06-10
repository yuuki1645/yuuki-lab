# 01 — マルコフ決定過程（MDP）

強化学習の問題は、ほぼすべて **MDP（Markov Decision Process）** として書けます。

## 5 要素

| 記号 | 名前 | 歩行 RL での例（exp_030） |
|------|------|---------------------------|
| \(S\) | 状態 | 関節角・速度・接触・IMU 等（観測はその部分ベクトル） |
| \(A\) | 行動 | 各関節へのトルク指令 |
| \(P(s'|s,a)\) | 遷移 | MuJoCo の物理シミュレーション |
| \(R(s,a,s')\) | 報酬 | `sim/reward.py` が返すスカラー |
| \(\gamma\) | 割引率 | `ppo.gamma_per_physics_step`（0.99） |

## マルコフ性

「次の状態は **今の状態と行動** だけで決まる」という仮定です。  
履歴を全部入れる必要がないので、方策は \(\pi(a|s)\) と書けます。

実際のロボットでは遅延・未観測があるため、**部分観測 MDP（POMDP）** に近いことが多いです。  
その場合でも、観測ベクトルを「状態の代理」として RL ではよく扱います。

## エージェントと環境のループ

```text
  ┌─────────┐  行動 a_t   ┌─────────┐
  │ 方策 π  │ ──────────→ │  環境   │
  │ (PPO)   │ ←────────── │ (MuJoCo)│
  └─────────┘  観測 s_t   └─────────┘
                    報酬 r_t
```

1. 環境が観測 \(s_t\) を返す  
2. 方策が行動 \(a_t \sim \pi(\cdot|s_t)\) を選ぶ  
3. 環境が \(s_{t+1}, r_t\) を返す  
4. 終了なら `reset`、そうでなければ繰り返し

## エピソード

`reset` から `terminated` または `truncated` までが **1 エピソード** です。

| 終了種別 | 意味 | 例 |
|---------|------|-----|
| **terminated** | タスク上の終了 | 転倒・異常接触 |
| **truncated** | 時間切れ | 30 s 到達 |

終了の扱いは advantage の計算に影響します → [practice/termination-and-truncation.md](../practice/termination-and-truncation.md)

## 何を「最適化」するか

エージェントの目的は、方策 \(\pi\) に従ったときの **期待 return（割引累積報酬）** を最大化することです。

\[
J(\pi) = \mathbb{E}_\pi \left[ \sum_{t=0}^{\infty} \gamma^t r_t \right]
\]

「どの \(r_t\) を入れるか」は **あなたの設計** です。これが報酬設計の本質です。

## よくある誤解

| 誤解 | 正しい理解 |
|------|------------|
| 観測 = 状態 | 観測はセンサ出力。真の状態はシミュ内部にもっと多い |
| 報酬が高い = 歩けている | train 報酬と eval 指標は別物（[practice/evaluation.md](../practice/evaluation.md)） |
| MDP を定義すれば学習できる | 報酬が誤ると最適方策も誤る（reward hacking） |

## 次に読む

- [02-returns-and-discount.md](02-returns-and-discount.md)
- [yuuki-lab/exp030-bridge.md](../yuuki-lab/exp030-bridge.md) — exp_030 への写像
