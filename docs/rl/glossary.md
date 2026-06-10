# 強化学習 用語集

本リポジトリの docs / 実験コードで頻出する用語です。アルファベット順。

## A

| 用語 | 意味 |
|------|------|
| **action（行動）** | エージェントが環境に出す指令。exp_030 では関節トルク（または目標角度）のベクトル。 |
| **actor** | 方策 \(\pi_\theta(a|s)\) を出力するネットワーク。 |
| **advantage（優位度）** | 「この行動は平均よりどれだけ良かったか」。\(A_t = Q(s_t,a_t) - V(s_t)\) のイメージ。PPO では GAE で推定。 |
| **on-policy** | 学習に使うデータが **現在の方策** で集めたものであること。PPO は on-policy。 |

## B

| 用語 | 意味 |
|------|------|
| **bootstrapping** | まだ終わっていないエピソードの将来報酬を、価値関数の推定値で補うこと。TD 学習の核心。 |
| **bias-variance trade-off** | 推定のブレ（分散）と系統誤差（バイアス）のトレードオフ。return 全体 vs TD の違い。 |

## C

| 用語 | 意味 |
|------|------|
| **critic** | 価値関数 \(V(s)\) または \(Q(s,a)\) を推定するネットワーク。 |
| **clip（PPO）** | 方策更新率 \(r_t(\theta)\) を \([1-\epsilon, 1+\epsilon]\) にクリップし、更新を安定化。 |

## D

| 用語 | 意味 |
|------|------|
| **discount factor \(\gamma\)** | 将来報酬の重み。0 に近いと近視眼的、1 に近いと長期重視。 |
| **Domain Randomization（DR）** | 学習時だけ物理パラメータをランダム化し、頑健性を上げる手法。eval は固定条件のまま。 |

## E

| 用語 | 意味 |
|------|------|
| **entropy bonus** | 方策のエントロピーに報酬を与え、探索を維持。係数は `entropy_coef`。 |
| **episode（エピソード）** | `reset` から `terminated` または `truncated` までの一連の相互作用。 |
| **exploration** | まだ試していない行動を試すこと。exploitation（既知の良い行動）とトレードオフ。 |

## G

| 用語 | 意味 |
|------|------|
| **GAE** | Generalized Advantage Estimation。advantage のバイアスと分散のバランスを \(\lambda\) で調整。 |

## M

| 用語 | 意味 |
|------|------|
| **MDP** | Markov Decision Process。状態・行動・遷移・報酬・割引で問題を定式化した枠組み。 |
| **markov property** | 次の状態が「今の状態と行動」だけで決まる（履歴不要）という仮定。 |

## O

| 用語 | 意味 |
|------|------|
| **observation（観測）** | エージェントが実際に見るベクトル。真の状態の部分観測であることが多い。exp_030 は 51 次元。 |
| **off-policy** | 古い方策や別方策で集めたデータで学習すること（DQN, SAC 等）。 |

## P

| 用語 | 意味 |
|------|------|
| **policy（方策）** | 状態から行動（または行動分布）への写像 \(\pi(a|s)\)。 |
| **PPO** | Proximal Policy Optimization。方策勾配を clip で安定化した on-policy algo。本線で使用。 |

## R

| 用語 | 意味 |
|------|------|
| **return（リターン）** | 割引累積報酬 \(G_t = \sum_k \gamma^k r_{t+k}\)。 |
| **reward hacking** | 意図しない抜け道で報酬だけを稼ぐ行動（すり足・転倒回避の変形など）。 |
| **reward shaping** | 学習を助けるための追加報酬項。設計ミスで最適行動が変わることがある。 |
| **rollout** | 方策で環境を進め、遷移系列を集めること。`rollout_steps` 分をバッファに貯める。 |

## T

| 用語 | 意味 |
|------|------|
| **terminated** | タスク上の自然終了（転倒・目標到達など）。bootstrap の扱いが `truncated` と異なる。 |
| **truncated** | 時間切れなどの人工終了。価値関数で続きを見積もることが多い。 |
| **TD error** | ベルマン方程式との差分。学習信号の源。 |

## V

| 用語 | 意味 |
|------|------|
| **value function \(V(s)\)** | 状態 \(s\) から方策 \(\pi\) に従ったときの期待 return。 |
| **VecEnv** | 複数環境を並列に `step` し、スループットを上げる仕組み。exp_030 は Subproc VecEnv。 |

## 関連

- [foundations/01-mdp.md](foundations/01-mdp.md) — MDP の詳細
- [algorithms/ppo.md](algorithms/ppo.md) — PPO 用語の文脈
