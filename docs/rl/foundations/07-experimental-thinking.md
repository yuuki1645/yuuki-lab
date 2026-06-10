# 07 — 実験の考え方

理論だけでは歩行は学習しません。**仮説を立て、公平に比較し、記録する** 文化が必要です。

## 1 run = 1 仮説

一度に複数の係数を変えると、何が効いたか分かりません。

| 良い例 | 悪い例 |
|--------|--------|
| `forward_reward_scale` だけ 50 → 55 | 報酬・LR・終了閾値を同時変更 |
| preset `reward=forward55` を 1 つ試す | 複数 preset を混ぜた独自設定 |

exp_030 の標準手順: [experiments/exp_030/workflow.md](../../experiments/exp_030_biped_ppo_walk/workflow.md)

## スモーク → 本番 → eval

```text
短い学習（smoke）→ eval_compare で方向確認
       ↓ Go
本番学習（prod）→ 自動 eval → 記録
```

スモークで No-Go なら、本番 5000 updates を回す前に切ります。

## 再現性

| 記録すべきもの | 場所（exp_030） |
|---------------|----------------|
| 全設定 | `runs/<run>/.hydra/config.yaml` |
| 学習 seed | `training.seed` / `DISPATCH_SEED` |
| eval 結果 | `eval_report.json` |
| W&B | run URL + summary |

## 統計的な見方

eval は 50 試行（10 seed × 5 ep）の mean ± std です。

- 1 run だけの改善は偶然の可能性  
- 複数 run を `eval_compare` で横並び  
- 主指標は **`displacement_x_mean`**（大きいほど前進）

## AI との分担

| AI に任せる | 人間が判断する |
|------------|---------------|
| 実装・ボイラープレート | 仮説の立て方 |
| 文献要約 | 報酬がタスクと一致しているか |
| デバッグの当たり | eval 結果の解釈 |
| コードリーディング補助 | 実機投入の安全 |

## 次に読む

- [practice/evaluation.md](../practice/evaluation.md)
- [practice/common-pitfalls.md](../practice/common-pitfalls.md)
- [yuuki-lab/exp030-bridge.md](../yuuki-lab/exp030-bridge.md)
