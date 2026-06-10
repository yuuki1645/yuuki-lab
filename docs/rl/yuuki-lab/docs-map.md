# ドキュメント関係図

yuuki-lab における RL 関連ドキュメントの全体像です。

```mermaid
flowchart TB
  subgraph root [リポジトリルート]
    TOP[README.md]
  end

  subgraph docs [docs/]
    DOCS_README[README.md]
    RL[rl/]
    EXP[experiments/]
    HUMAN[human_*.md]
    TIMING[control_timing_human_rl.md]
  end

  subgraph rl_detail [docs/rl/]
    FOUND[foundations/]
    ALGO[algorithms/]
    PRAC[practice/]
    YL[yuuki-lab/]
  end

  subgraph exp030 [docs/experiments/exp_030/]
    E30R[reward.md]
    E30T[termination.md]
    E30W[workflow.md]
  end

  subgraph code [コード]
    TRAIN[train.py]
    REWARD[sim/reward.py]
    AGENT[rl/agent.py]
  end

  TOP --> RL
  TOP --> EXP
  DOCS_README --> RL
  DOCS_README --> EXP
  RL --> FOUND
  RL --> ALGO
  RL --> PRAC
  RL --> YL
  YL --> EXP
  EXP --> E30R
  EXP --> E30T
  EXP --> E30W
  E30R --> REWARD
  E30W --> TRAIN
  ALGO --> AGENT
  PRAC --> E30R
  HUMAN --> E30R
  TIMING --> PRAC
```

## 役割の早見表

| パス | 役割 | 更新タイミング |
|------|------|---------------|
| `docs/rl/` | 汎用・学習用 | algo 理解を深めたとき |
| `docs/experiments/<exp>/` | 実験正本 | 報酬・終了・eval を変えたとき |
| `experiments/<exp>/README.md` | 入口 | 新 exp・手順変更時 |
| `experiments/<exp>/AGENTS.md` | AI 向け落とし穴 | 設計判断を変えたとき |

## 人体・実機 docs との関係

| ドキュメント | RL との接続 |
|-------------|------------|
| [human_joint_kinematics.md](../../human_joint_kinematics.md) | 歩行 shaping の意味 |
| [human_joint_torque.md](../../human_joint_torque.md) | トルク飽和・effort penalty |
| [control_timing_human_rl.md](../../control_timing_human_rl.md) | 50 Hz 制御 step |
| [sim_human_comparison.md](../../sim_human_comparison.md) | 観測・軸の対応 |
