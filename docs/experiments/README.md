# 実験ドキュメント一覧

各実験の **詳細解説**（ワークフロー・報酬・終了条件・コードリーディング・実装）を格納する。  
配置場所はリポジトリルートの **`yuuki-lab/docs/experiments/`**。

## 運用方針

- 各 `mujoco-sim/mujoco_rl_sim/experiments/exp_*` の **README.md** は入口（概要・最短手順・本 docs へのリンク）に留める。
- **報酬・終了・ワークフロー・実装詳細** の正本は `docs/experiments/<exp_name>/` に置く（ファイル分割推奨）。
- 実験フォルダはスタンドアロンコピー戦略を維持する。

| 実験 | 入口 | 実験フォルダ |
|------|------|--------------|
| exp_030_biped_ppo_walk | [README](exp_030_biped_ppo_walk/README.md) | [experiments/exp_030_biped_ppo_walk/](../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) |
| isaac_biped_ppo_walk | [README](isaac_biped_ppo_walk/README.md) | [isaac-lab/source/yuuki_isaac_lab/.../biped_ppo_walk/](../../isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/direct/biped_ppo_walk/) |

新規 `exp_*` を追加するときは、本ディレクトリに `<exp_name>/` を作成し、実験 README からリンクする。
