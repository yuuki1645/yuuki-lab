# よくある落とし穴

## 報酬・タスク

| 落とし穴 | 症状 | 対策 |
|---------|------|------|
| **Reward hacking** | train 報酬↑、eval 前進↓ | eval 主指標で判断、[reward-design.md](reward-design.md) |
| **報酬地獄** | 係数調整が終わらない | ENABLE で項を切る、1 軸変更 |
| **ホップと歩行の混同** | 飛翔中 IMU で前進 | 片足支持ゲート、flight penalty |
| **すり足** | 報酬は取れるが変な歩き | `double_support_penalty` |

## 学習・algo

| 落とし穴 | 症状 | 対策 |
|---------|------|------|
| train 曲線だけ見る | 「学習できた」錯覚 | [evaluation.md](evaluation.md) |
| ハイパラと報酬を同時変更 | 何が効いたか不明 | 1 run = 1 仮説 |
| entropy 枯渇 | 早期に同じ動きの繰り返し | `entropy_coef` / `std_min` |
| advantage 爆発 | 更新が不安定 | `adv_clip`, `reward_clip` |

## シミュ・実装

| 落とし穴 | 症状 | 対策 |
|---------|------|------|
| terminated / truncated 混同 | advantage が歪む | [termination-and-truncation.md](termination-and-truncation.md) |
| 観測次元変更後に旧 ckpt | load エラー | contract validate |
| VecEnv で viewer 期待 | 動かない | `num_envs=1` or debug preset |

## AI 利用時

| 落とし穴 | 対策 |
|---------|------|
| AI の報酬案をそのまま採用 | [glossary.md](../glossary.md) で用語確認、eval で検証 |
| docs 未更新のままコード変更 | `reward.md` / `termination.md` を正本として更新 |
| 複数ファイルを一度に大改修 | 小さな PR / 1 仮説ずつ |

## 次に読む

- [foundations/07-experimental-thinking.md](../foundations/07-experimental-thinking.md)
- [yuuki-lab/exp030-bridge.md](../yuuki-lab/exp030-bridge.md)
