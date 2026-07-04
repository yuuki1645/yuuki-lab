# BipedPpoWalk — Manager-Based 版

**Yuuki Lab 両脚交互片脚歩行 PPO** の Isaac Lab **ManagerBasedRLEnv** 移植版です。  
MDP（報酬・観測 54 次元・終了条件）は [Direct 版](../direct/biped_ppo_walk/) と同一で、実装のみ Manager ワークフローに分解しています。

詳細（観測レイアウト・報酬設計・exp_030 対応表など）は Direct 版 README を参照してください:

- [tasks/direct/biped_ppo_walk/README.md](../direct/biped_ppo_walk/README.md)

---

## タスク ID

| Task ID | 用途 |
|---------|------|
| `YuukiLab-BipedPpoWalk-v0` | 学習（Manager-Based） |
| `YuukiLab-BipedPpoWalk-Play-v0` | 再生・録画 |

---

## Direct 版との差分

| 項目 | Direct | Manager-Based |
|------|--------|---------------|
| 環境クラス | `DirectRLEnv` | `ManagerBasedRLEnv` |
| 報酬・観測 | env 内メソッド | Manager 項（`mdp/`） |
| ログ dir | `logs/rsl_rl/biped_ppo_walk/` | `logs/rsl_rl/biped_ppo_walk_manager/` |
| MDP ロジック | 同一（`direct/biped_ppo_walk/mdp` を再利用） | |

---

## ディレクトリ構成

```
biped_ppo_walk/
├── biped_ppo_walk_env.py       # BipedPpoWalkEnv（エピソード状態 + eval 互換）
├── biped_ppo_walk_env_cfg.py   # Scene / Actions / Obs / Reward / Termination
├── agents/rsl_rl_ppo_cfg.py
└── mdp/
    ├── episode_state.py        # 位相・進捗バッファ
    ├── actions.py              # 中立角基準の関節位置写像
    ├── observations.py         # 54 次元観測
    ├── rewards.py              # compute_step_reward ラップ
    ├── terminations.py
    └── events.py               # リセット + 関節ノイズ
```

---

## 実行例

```powershell
# スモーク（専用ラッパー）
python scripts/manager_based/smoke.py --headless --num_envs 4 --steps 200

# 学習
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --headless --num_envs 64 --max_iterations 5

# 本番
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --headless --num_envs 4096

# 評価
python scripts/eval_biped_walk.py --task YuukiLab-BipedPpoWalk-v0 --load_run <run_dir_name>

# 再生
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-Play-v0 --load_run <run_dir_name>
```

---

## 変更時の注意

- 報酬・観測・終了の **係数・ロジック** を変える場合は `direct/biped_ppo_walk/mdp/` が正本。Manager 側はラップ層のみ更新するか、共有 mdp を直接編集する。
- 観測次元を変えた場合は Direct 版と **両方** の登録・PPO 設定を整合させる。
- Python ソースの docstring は **ASCII / 英語** を推奨（Windows 環境でのエンコーディング問題回避）。日本語説明は本 README または Direct 版 README に書く。
