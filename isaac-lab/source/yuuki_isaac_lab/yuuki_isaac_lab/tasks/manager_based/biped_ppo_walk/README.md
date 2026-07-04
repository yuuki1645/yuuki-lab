# BipedPpoWalk — Manager-Based 版

**Yuuki Lab 両脚交互片脚歩行 PPO** の Isaac Lab **ManagerBasedRLEnv** 実装です。  
MDP は manager-based ワークフローに沿って **項ごとの `RewTerm`** に分解され、Direct 版とは独立したコードベースです。

---

## タスク ID

| Task ID | 用途 |
|---------|------|
| `YuukiLab-BipedPpoWalk-v0` | 学習（Manager-Based） |
| `YuukiLab-BipedPpoWalk-Play-v0` | 再生・録画 |

---

## 設計方針

| 項目 | 内容 |
|------|------|
| 環境クラス | `ManagerBasedRLEnv` |
| 報酬 | `RewardsCfg` の個別 `RewTerm`（`mdp/rewards.py`） |
| 係数 | `BipedRewardCfg` → `_sync_reward_weights_from_cfg()` で weight に反映 |
| 共有状態 | `mdp/episode_state.py`（歩行位相・ゲート・マイルストーン） |
| Direct 版 | 別タスクとして残存（コード共有なし） |

---

## ディレクトリ構成

```
biped_ppo_walk/
├── biped_ppo_walk_env.py       # BipedPpoWalkEnv + episode state
├── biped_ppo_walk_env_cfg.py   # Scene / RewardsCfg / BipedRewardCfg
├── agents/rsl_rl_ppo_cfg.py
└── mdp/
    ├── actuators.py            # 関節名・ctrlrange
    ├── action.py               # [-1,1] → 関節位置目標
    ├── gait.py                 # 着地エッジ・交互歩行コンテキスト
    ├── pose.py / obs_norm.py
    ├── episode_state.py        # スナップショット + バッファ
    ├── rewards.py              # Manager 報酬項（1 関数 = 1 RewTerm）
    ├── reward_utils.py         # マイルストーン・forward ゲート
    ├── observations.py
    ├── terminations.py
    └── events.py
```

---

## 報酬の変更方法

1. **係数だけ変える** → `biped_ppo_walk_env_cfg.py` の `BipedRewardCfg` を編集（`__post_init__` が weight を同期）
2. **項を無効化** → 対応する `enable_*` を `False`、または `self.rewards.<term> = None`
3. **ロジックを変える** → `mdp/rewards.py` の該当関数を編集
4. **新項を追加** → `mdp/rewards.py` に関数追加 + `RewardsCfg` に `RewTerm` 追加

---

## 実行例

```powershell
# スモーク
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

- 観測次元を変えた場合は PPO 設定（`agents/rsl_rl_ppo_cfg.py`）も更新する
- 報酬 sweep は `RewardsCfg` の weight または `BipedRewardCfg` の係数を 1 軸ずつ変更するのが推奨
