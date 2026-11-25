# 実験ドキュメント一覧

各実験の **詳細解説**（ワークフロー・報酬・終了条件・コードリーディング・実装）を格納する。  
配置場所はリポジトリルートの **`yuuki-lab/docs/experiments/`**。

## 運用方針

- **強化学習の本線は Isaac Lab の `YuukiLab-BipedWalk-v0`**。手順と仕様は [isaac-lab/README.md](../../isaac-lab/README.md) と `biped_walk_env_cfg.py`。このディレクトリには Isaac の現行実験フォルダを置かない。
- MuJoCo `exp_*` は参照です。現行タスクの仕様ではありません。
- 各実験フォルダの **README.md** は入口（概要・最短手順・本 docs へのリンク）に留める。

| 実験 | 位置づけ | 入口 | コード |
|------|----------|------|--------|
| exp_030_biped_ppo_walk | 参照（旧 MuJoCo 歩行） | [README](exp_030_biped_ppo_walk/README.md) | [experiments/exp_030_biped_ppo_walk/](../../mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk/) |

MuJoCo `exp_*` を追加するときは、本ディレクトリに対応フォルダを作成し、実験 README からリンクする。
