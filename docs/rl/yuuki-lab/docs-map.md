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

  subgraph isaac_code [isaac-lab 本線]
    ISAAC_CFG[biped_walk_env_cfg.py]
    ISAAC_TRAIN[scripts/rsl_rl/train.py]
  end

  subgraph exp030 [docs/experiments/exp_030/ 参照]
    E30R[reward.md]
    E30T[termination.md]
  end

  subgraph code_ref [コード参照 MuJoCo]
    TRAIN[train.py]
    REWARD[sim/reward.py]
  end

  TOP --> RL
  TOP --> EXP
  DOCS_README --> RL
  DOCS_README --> EXP
  RL --> FOUND
  RL --> ALGO
  RL --> PRAC
  RL --> YL
  YL --> isaac_code
  YL --> exp030
  EXP --> E30R
  ISAAC_CFG --> ISAAC_TRAIN
  E30R --> REWARD
  ALGO --> ISAAC_TRAIN
  PRAC --> ISAAC_CFG
  HUMAN --> ISAAC_CFG
  TIMING --> PRAC
```

## 役割の早見表

| パス | 役割 | 更新タイミング |
|------|------|---------------|
| `docs/rl/` | 汎用・学習用 | algo 理解を深めたとき |
| `isaac-lab/` の `biped_walk` | **本線**の仕様と学習 | 報酬・終了・観測を変えたとき |
| `docs/experiments/exp_030_*/` | MuJoCo 参照 | 背景の報酬・終了を読むとき |
| `isaac-lab/` | 本線コード | 学習・報酬・終了を変えたとき |
| `mujoco-sim/.../exp_*/README.md` | MuJoCo 入口 | レガシー手順変更時 |
| `.cursor/skills/rl-improvement-loop/` | AI 改善ループ | 本線ワークフロー変更時 |

## 人体・実機 docs との関係

| ドキュメント | RL との接続 |
|-------------|------------|
| [human_joint_kinematics.md](../../human_joint_kinematics.md) | 歩行 shaping の意味 |
| [human_joint_torque.md](../../human_joint_torque.md) | トルク飽和・effort penalty |
| [control_timing_human_rl.md](../../control_timing_human_rl.md) | 50 Hz 制御 step |
| [sim_human_comparison.md](../../sim_human_comparison.md) | 観測・軸の対応 |
