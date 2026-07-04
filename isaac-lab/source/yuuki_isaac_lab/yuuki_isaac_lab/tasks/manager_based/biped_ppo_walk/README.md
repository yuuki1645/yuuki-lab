# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Manager-Based 版 BipedPpoWalk タスクの README 入口。

詳細は Direct 版 README を参照:
``tasks/direct/biped_ppo_walk/README.md``

## タスク ID

| Task ID | 用途 |
|---------|------|
| ``YuukiLab-BipedPpoWalk-v0`` | 学習（Manager-Based） |
| ``YuukiLab-BipedPpoWalk-Play-v0`` | 再生・録画 |

## Direct 版との差分

| 項目 | Direct | Manager-Based |
|------|--------|---------------|
| 環境クラス | ``DirectRLEnv`` | ``ManagerBasedRLEnv`` |
| 報酬・観測 | env 内メソッド | Manager 項（``mdp/``） |
| ログ dir | ``biped_ppo_walk/`` | ``biped_ppo_walk_manager/`` |
| MDP ロジック | 同一（direct/mdp を再利用） |

## 実行例

```powershell
# スモーク
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --headless --num_envs 64 --max_iterations 5

# 本番
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --headless --num_envs 4096

# 評価
python scripts/eval_biped_walk.py --task YuukiLab-BipedPpoWalk-v0 --load_run <run_dir_name>
```
