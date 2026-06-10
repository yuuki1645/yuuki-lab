# 報酬設計

報酬は **エージェントに何を学ばせるか** の設計図です。物理シミュが正しくても、報酬がズレれば歩けません。

## スパース vs デンス

| 種類 | 例 | 長所 | 短所 |
|------|-----|------|------|
| **スパース** | ゴール到達時のみ +1 | 目標が明確 | 学習が極端に遅い |
| **デンス** | 毎ステップの前進量 | 学習しやすい | 意図しない最適行動（ハック） |

歩行では **デンスな前進報酬 + 必要最小限の shaping** が一般的です。

## Reward shaping

目標に近づくための **中間報酬** です。

| 例（exp_030） | 意図 |
|--------------|------|
| `forward_imu` | 前進 |
| `alternating_landing_bonus` | 交互着地 |
| `double_support_penalty` | すり足抑制 |
| `effort_penalty` | 無駄な筋力を抑える |

### shaping のリスク

最適方策は **shaping 付き MDP** の最適解になります。  
本当に欲しい行動と一致しないと、報酬は高いが eval は悪い、という状態になります。

→ [common-pitfalls.md](common-pitfalls.md)

## 報酬地獄（coefficient interference）

複数の shaping 項を同時に有効にすると、係数が互いに干渉し、チューニングが爆発します。

exp_030 の対策:

- `reward.enable_*` で **項ごとに ON/OFF**
- 既定 preset `baseline` はミニマル報酬
- **1 run = 1 仮説** で 1 項ずつ検証

実験正本: [experiments/exp_030/reward.md](../../experiments/exp_030_biped_ppo_walk/reward.md)

## ゲート条件

「いつ主報酬が 0 になるか」が行動を強く制約します。

| ゲート | 効果 |
|--------|------|
| 片足支持時のみ前進 | すり足・両足這いを防ぐ |
| 直立閾値 `forward_min_upright` | 転倒しながらの IMU 前進を防ぐ |
| 飛翔中 IMU 減衰 | ホップ主線との分離 |

## 終了ペナルティとの境界

| 種類 | タイミング | 例 |
|------|-----------|-----|
| ステップ報酬 | 毎制御ステップ | `forward_imu`, `effort_penalty` |
| 終了ペナルティ | エピソード終了時 | 転倒ペナルティ（`termination.py`） |
| 接触ペナルティ | 物理ステップごと | 床すり接触（`env.py`） |

報酬合成の境界は実験 docs の合成式を参照してください。

## 設計チェックリスト

1. **eval 指標と一致しているか**（train 報酬だけ見ない）  
2. **1 回の変更は 1 係数 or 1 ENABLE**  
3. **コピー元 exp と diff を docs に書いたか**  
4. **歩行位相の用語は [human_joint_kinematics.md](../../human_joint_kinematics.md) と整合しているか**

## 次に読む

- [evaluation.md](evaluation.md)
- [termination-and-truncation.md](termination-and-truncation.md)
- [foundations/01-mdp.md](../foundations/01-mdp.md)
