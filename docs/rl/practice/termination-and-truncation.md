# 終了条件（terminated / truncated）

Gymnasium ではエピソード終了を **2 種類** に分けます。advantage 計算と bootstrap に影響します。

## 用語

| 種別 | 意味 | 例（歩行） |
|------|------|-----------|
| **terminated** | タスク上の自然終了 | 転倒、異常姿勢、禁止接触 |
| **truncated** | 人工的な打ち切り | 最大ステップ（30 s）到達 |

## bootstrap への影響

TD / GAE では「エピソードが続くなら $V(s')$ を使う」という見積もりをします。

| 終了 | $V(s_{t+1})$ |
|------|----------------|
| 通常 | 使う |
| **terminated** | **0**（これ以上報酬なし） |
| **truncated** | 使う（時間切れでも続きがありうる） |

terminated を truncated と混同すると、advantage が歪みます。

## 終了ペナルティ

転倒時に **大きな負報酬** を一度だけ与える設計が一般的です。

- エージェントに「転倒を避ける」勾配を与える  
- ただしペナルティだけに頼ると、**動かない・安全な姿勢で止まる** などの副作用もありうる  

exp_030 正本: [experiments/exp_030/termination.md](../../experiments/exp_030_biped_ppo_walk/termination.md)

## 終了しないペナルティ

床すり接触など、**毎ステップ積算** されるペナルティは `env.py` 側で扱います。  
終了ペナルティと混同しないこと（ログキーも別）。

## 設計のコツ

| 原則 | 理由 |
|------|------|
| 終了理由をログに残す | `termination_breakdown` で eval 時に分析 |
| 閾値は config 化 | Hydra `conf/termination/` |
| 終了を変えたら docs 更新 | [experiments/AGENTS.md](../../../mujoco-sim/mujoco_rl_sim/experiments/AGENTS.md) |

## 次に読む

- [foundations/04-temporal-difference.md](../foundations/04-temporal-difference.md)
- [reward-design.md](reward-design.md)
