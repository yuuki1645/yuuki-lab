# 06 — 関数近似（ニューラルネット）

## なぜ必要か

ロボット歩行の状態空間は連続・高次元です。タブラー（全状態を表で持つ）では不可能なので、**ニューラルネットで方策・価値を近似**します。

| ネットワーク | 近似するもの | exp_030 |
|-------------|-------------|---------|
| Actor（方策） | \(\pi_\theta(a|s)\) | MLP 256→256→128 |
| Critic（価値） | \(V_\phi(s)\) | 同上構造 |

## 深層 RL の落とし穴

関数近似を入れると、理論上の収束保証は弱くなります。

| 問題 | 症状 |
|------|------|
| **致命的な相互干渉** | ある状態の更新が別状態の推定を壊す |
| **非定常性** | 方策が変わるとデータ分布も変わる（on-policy の理由） |
| **スケーリング** | 観測・報酬のスケールが学習に効く |

## 観測の正規化

生の関節角・速度をそのまま入れると学習が不安定になりやすいです。  
exp_030 では `sim/observation.py` で正規化・クリップを行います。

→ [practice/observation-and-normalization.md](../practice/observation-and-normalization.md)

## 報酬・advantage のクリップ

exp_030 の PPO 設定:

| パラメータ | 既定値 | 目的 |
|-----------|--------|------|
| `reward_clip` | 20.0 | 極端な報酬 spike を抑える |
| `adv_clip` | 10.0 | advantage の外れ値を抑える |
| `max_grad_norm` | 0.5 | 勾配爆発を防ぐ |

## on-policy が大事な理由

方策 \(\theta\) で集めたデータで、方策を更新します。  
古い方策のデータで何度も更新すると（off-policy 的に使うと）、近似誤差が蓄積しやすいです。

PPO は **同じ rollout を数 epoch 再利用** しますが、clip で更新幅を制限して on-policy 性を保ちます。

## 次に読む

- [algorithms/policy-gradient.md](../algorithms/policy-gradient.md)
- [07-experimental-thinking.md](07-experimental-thinking.md)
