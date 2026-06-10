# 05 — 探索と活用（exploration / exploitation）

## トレードオフ

- **exploration（探索）** … まだ試していない行動を試す  
- **exploitation（活用）** … 今わかっている良い行動を使う  

学習初期は探索が必要、収束期は活用が支配的、というバランスが要ります。

## 多腕バンディット（SB 第2章）

最も単純な RL 問題です。複数のスロットマシン（腕）から、試行錯誤で報酬の高い腕を見つけます。

歩行 RL でも本質は同じです。「この報酬 shaping を入れると学習が速いか」は、バンディット的な試行になります。

## 連続制御での探索

離散の $\epsilon$-greedy の代わりに、連続制御では次が一般的です。

| 手法 | 仕組み |
|------|--------|
| **確率的方策** | ガウスからサンプル → 自然にランダム性 |
| **entropy bonus** | 方策のエントロピーに報酬 → 分布を広く保つ |
| **行動ノイズ** | 平均にノイズを加算（方策外） |

exp_030 の PPO は **ガウス方策 + entropy_coef=0.05** で探索を維持します。

## entropy が下がりすぎると

方策の標準偏差が小さくなり、**同じ行動の繰り返し** になります。

- 早期収束に見えても、より良い歩行パターンを試さない  
- `entropy_coef` を上げる、または `std_min` を確認  

## 探索と Domain Randomization

DR は「環境側」のランダム化です。方策が多様な物理条件に耐えるよう、**状態空間の探索を補完**します。

→ [practice/domain-randomization.md](../practice/domain-randomization.md)

## 次に読む

- [06-function-approximation.md](06-function-approximation.md)
- [practice/common-pitfalls.md](../practice/common-pitfalls.md)
