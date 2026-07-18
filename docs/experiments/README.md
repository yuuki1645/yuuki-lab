# 実験ドキュメント一覧

各実験の **詳細解説**（ワークフロー・報酬・終了条件・コードリーディング・実装）を格納する。  
配置場所はリポジトリルートの **`yuuki-lab/docs/experiments/`**。

## 運用方針

- **強化学習の本線は Isaac Lab**（`isaac_biped_ppo_walk`）。日常の学習・eval・改善ループはこちら。
- MuJoCo `exp_*` は参照・レガシー。報酬設計の背景を読むときに使う。
- 各実験フォルダの **README.md** は入口（概要・最短手順・本 docs へのリンク）に留める。
- **報酬・終了・ワークフロー・実装詳細** の正本は `docs/experiments/<name>/` に置く（ファイル分割推奨）。

| 実験 | 位置づけ | 入口 | コード |
|------|----------|------|--------|
| **isaac_biped_ppo_walk** | **本線** | [README](isaac_biped_ppo_walk/README.md) | [isaac-lab/.../biped_ppo_walk/](../../isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/direct/biped_ppo_walk/) |
| exp_030_biped_ppo_walk | 参照（旧 MuJoCo 本線） | [README](exp_030_biped_ppo_walk/README.md) | [experiments/exp_030_biped_ppo_walk/](../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) |

新規 Isaac タスクや MuJoCo `exp_*` を追加するときは、本ディレクトリに対応フォルダを作成し、実験 README からリンクする。
