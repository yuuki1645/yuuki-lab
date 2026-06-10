# Domain Randomization（DR）

学習時だけ **物理パラメータや初期条件をランダム化** し、方策の頑健性を上げる手法です。

## 目的

| 効果 | 説明 |
|------|------|
| sim-to-real 耐性 | 実機とシミュのパラメータズレに強くする |
| 過学習抑制 | 単一の物理設定にフィットしにくい |

## exp_030 の DR（v1）

| 項目 | 内容 |
|------|------|
| 対象 | 初期姿勢ノイズ、足底摩擦、actuator kp/kv |
| タイミング | 学習 `reset` のみ |
| eval | **変更なし**（固定プロトコル） |
| 既定 | ON（`training.training_dr=false` で無効） |

実装: `sim/domain_randomization.py`

## eval との関係

DR は **学習の難易度を上げる** ことが多いです。  
train 曲線が下がっても、eval が上がる（汎化が進む）ケースがあります。  
逆に DR なしで train だけ見ると過信しやすいです。

## visualize / analyze では DR なし

可視化・手動 eval は **決定的 stand** で動かします。  
学習時のランダム性と混同しないこと。

## 次に読む

- [evaluation.md](evaluation.md)
- [experiments/exp_030/training-parallel.md](../../experiments/exp_030_biped_ppo_walk/training-parallel.md)
