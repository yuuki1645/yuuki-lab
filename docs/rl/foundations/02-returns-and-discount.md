# 02 — リターンと割引

## リターン（return）

時刻 \(t\) からの **割引累積報酬** を \(G_t\) と書きます。

\[
G_t = r_t + \gamma r_{t+1} + \gamma^2 r_{t+2} + \cdots
\]

方策 \(\pi\) の **期待リターン** \(V^\pi(s) = \mathbb{E}[G_t \mid s_t=s]\) が価値関数です。

## 割引率 \(\gamma\) の意味

| \(\gamma\) | 挙動 |
|------------|------|
| 0 に近い | 目の前の報酬だけ重視（近視眼的） |
| 1 に近い | 遠い将来も重視（長期的） |
| 1.0（無割引） | 無限ホライズンでは発散しうるため、有限エピソードか \(\gamma<1\) が必要 |

exp_030 では物理ステップごとに \(\gamma=0.99\) を適用しています（`conf/ppo/default.yaml` の `gamma_per_physics_step`）。

制御ステップ（50 Hz）と物理ステップ（500 Hz）の関係は [control_timing_human_rl.md](../../control_timing_human_rl.md) を参照。

## 有限ホライズン

exp_030 のエピソードは最大 30 s（`MAX_STEPS_PER_EPISODE`）で **truncated** されます。  
無限和ではなく「それまでの累積」として return を計算します。

## 報酬のスケール

return の大きさは **報酬のスケールと \(\gamma\)** に依存します。

- 報酬係数を 10 倍しても、最適方策は通常変わらない（同じ順序なら）
- ただし学習の数値安定性（勾配の大きさ）は変わる
- PPO では `reward_clip` で 1 ステップ報酬をクリップしている（exp_030）

## エピソード報酬 vs ステップ報酬

| 指標 | 用途 |
|------|------|
| `ep_return`（エピソード合計） | 学習曲線のざっくり確認 |
| ステップごとの `reward_total` | どの項が効いているかのデバッグ |
| eval `displacement_x_mean` | **採用判断**（train 報酬とは別プロトコル） |

train の `ep_return` が上がっても eval が上がらない場合、報酬と真の目標がずれています。

## 次に読む

- [03-policy-and-value.md](03-policy-and-value.md)
- [practice/reward-design.md](../practice/reward-design.md)
