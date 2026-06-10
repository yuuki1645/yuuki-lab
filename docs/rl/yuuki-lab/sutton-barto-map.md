# Sutton & Barto ↔ rl/foundations 対応表

Sutton & Barto『強化学習』第2版を **学び直す** ときの、章と本リポジトリ docs の対応です。

## 推奨章（優先順）

| 優先 | SB 章 | rl/ ファイル | 読んだら |
|------|-------|-------------|---------|
| ★★★ | 第3章 MDP | [01-mdp.md](../foundations/01-mdp.md), [02-returns-and-discount.md](../foundations/02-returns-and-discount.md) | [exp030-bridge.md](exp030-bridge.md) |
| ★★★ | 第13章 方策勾配法 | [policy-gradient.md](../algorithms/policy-gradient.md) | [ppo.md](../algorithms/ppo.md) |
| ★★☆ | 第6章 TD学習 | [04-temporal-difference.md](../foundations/04-temporal-difference.md) | PPO の GAE |
| ★★☆ | 第4章 動的計画法 | [03-policy-and-value.md](../foundations/03-policy-and-value.md) | critic の意味 |
| ★☆☆ | 第2章 多腕バンディット | [05-exploration.md](../foundations/05-exploration.md) | sweep の考え方 |
| ★☆☆ | 第9〜11章 関数近似 | [06-function-approximation.md](../foundations/06-function-approximation.md) | MLP 方策 |

## 飛ばしてよい章（最初の一巡）

| 章 | 理由 |
|----|------|
| 第5章 モンテカルロ法 | PPO は TD / GAE 系 |
| 第7〜8章 | タブラー拡張。直感は得られるが優先度低 |
| 第12章 | エリート法など。本線は PPO |
| 第14〜17章 | 心理学・応用。必要になったら |

## 1 週間プラン（例）

| 日 | SB | rl/ + 実践 |
|----|-----|-----------|
| 1 | 第3章 | 01-mdp, 02-returns |
| 2 | 第4章 | 03-policy-and-value |
| 3 | 第6章 | 04-temporal-difference |
| 4 | 第13章前半 | policy-gradient |
| 5 | 第13章後半 + PPO 論文 | ppo.md |
| 6 | — | exp030-bridge + reward.md |
| 7 | — | smoke 学習 + eval_compare |

## SB を読みながら書くメモ（テンプレ）

各章の末尾に 3 行だけ書くと定着します。

```text
1. この章の核心を一言で:
2. exp_030 ではどこに効くか:
3. まだ分からないこと:
```

## 次に読む

- [foundations/README.md](../foundations/README.md)
- [references.md](../references.md)
