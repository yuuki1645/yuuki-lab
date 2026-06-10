# 評価（train 指標 vs eval 指標）

学習中の曲線と、採用判断用の eval は **別物** として設計します。

## なぜ分けるか

| 指標 | 最適化対象 | 問題 |
|------|-----------|------|
| train `ep_return` | PPO が直接最大化 | 報酬ハックで上がることがある |
| eval 主指標 | 人間が定義したタスク成功度 | 報酬とズレうるが、**採用判断に使う** |

exp_030 の鉄則: **良し悪しは `eval/displacement_x_mean`**（大きいほど前進）。

## 固定プロトコル

eval は学習時と **意図的に条件を揃えます**。

| 項目 | 学習 | eval（exp_030 v0） |
|------|------|-------------------|
| 方策 | 確率的（探索） | **deterministic** |
| DR | ON（既定） | **OFF** |
| 初期ノイズ | エピソードごと | **固定レンジ・固定 seed 集合** |
| 試行数 | — | 50（10 seed × 5 ep） |

仕様正本: [experiments/exp_030/evaluation.md](../../experiments/exp_030_biped_ppo_walk/evaluation.md)

## 比較のやり方

1. 各 run の `eval_report.json` を生成（学習後自動 or `scripts/eval.py`）  
2. `scripts/eval_compare.py` で横並び  
3. 主指標の mean と std を見る（1 run だけで断定しない）

## W&B summary との関係

W&B の `eval/displacement_x_mean` は採点の補助。  
**正本は `eval_report.json`** と run ディレクトリ内の `.hydra/config.yaml` です。

## よくある誤り

| 誤り | 正しい做法 |
|------|-----------|
| train 曲線だけで「歩けた」と判断 | eval を必ず見る |
| eval なしで sweep ランキング | 全 run に同一 eval 仕様 |
| 学習中のベスト ckpt を eval しない | `final.pt` または明示的な ckpt 選択ルール |

## 次に読む

- [foundations/07-experimental-thinking.md](../foundations/07-experimental-thinking.md)
- [common-pitfalls.md](common-pitfalls.md)
