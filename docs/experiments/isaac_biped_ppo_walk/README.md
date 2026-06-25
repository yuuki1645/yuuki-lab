# Isaac Lab — biped_ppo_walk 実験ドキュメント

Isaac Sim 上の二足歩行 PPO（`YuukiLab-BipedPpoWalk-Direct-v0`）の実験正本。

## 入口

| ドキュメント | 内容 |
|--------------|------|
| [iterations.md](iterations.md) | **反復改善ログ**（分析・判断・実装・結果） |
| タスク README | `isaac-lab/source/yuuki_isaac_lab/.../biped_ppo_walk/README.md` |
| 報酬設計の背景（参照のみ） | [exp_030 reward.md](../exp_030_biped_ppo_walk/reward.md) |

## 現在の目的（例）

**30 秒エピソード内で +X 方向に 5 m 前進する交互片脚歩行**

達成条件（Isaac eval）:
- `eval_biped_walk.py` の **Success rate >= 5 m ≥ 80%**
- 平均 `episode_displacement_x` が安定的に 4 m 以上

## エージェントスキル

反復改善ループは `.cursor/skills/rl-improvement-loop/SKILL.md` に従う。  
`@rl-improvement-loop` で明示呼び出し、または RL 改善・学習反復の文脈で自動適用。

## クイックコマンド

```powershell
cd isaac-lab

# スモーク
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-Direct-v0 --headless --num_envs 64 --max_iterations 5

# 評価
python scripts/eval_biped_walk.py --load_run <run_dir> --episodes 10 --num_envs 64
```
