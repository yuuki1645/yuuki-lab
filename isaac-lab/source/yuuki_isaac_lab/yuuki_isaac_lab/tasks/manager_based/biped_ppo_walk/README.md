# BipedPpoWalk — Manager-Based 版

**Yuuki Lab 両脚交互片脚歩行 PPO** の Isaac Lab **ManagerBasedRLEnv** 実装です（本線タスクの Manager 版）。  
Direct 版とは独立したコードベースで、Isaac Lab の Manager ワークフローに沿って MDP を構成しています。

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
| 環境クラス | `ManagerBasedRLEnv` + `BipedEpisodeState`（歩行位相バッファ） |
| 報酬 | `RewardsCfg` の個別 `RewTerm`（weight が係数） |
| 観測 | `ObservationsCfg` の 17 個の `ObsTerm`（連結で 54 次元） |
| 閾値 | `walk_params` / `observation_params` / `termination_params` |
| Direct 版 | 別タスク（コード共有なし） |

---

## ディレクトリ構成

```
biped_ppo_walk/
├── biped_ppo_walk_env.py
├── biped_ppo_walk_env_cfg.py   # Scene / Obs / Reward / Event / Termination
├── agents/rsl_rl_ppo_cfg.py
└── mdp/
    ├── walk_params.py          # 報酬ロジック用閾値
    ├── observation_params.py   # 観測正規化スケール
    ├── episode_state.py        # スナップショット + バッファ
    ├── observations.py         # 17 ObsTerm 関数
    ├── rewards.py              # RewTerm 関数
    ├── events.py               # reset + joint noise
    └── ...
```

---

## 設定の触り方

| 変更内容 | 編集先 |
|----------|--------|
| 報酬の強度 | `RewardsCfg.<term>.weight` |
| 報酬ロジックの閾値 | `walk_params` |
| 観測の正規化 | `observation_params` |
| 観測項の ON/OFF | `ObservationsCfg.policy.<term> = None` |
| 終了条件 | `termination_params` + `TerminationsCfg` |
| リセット | `EventsCfg`（`reset_robot` / `reset_joint_noise`） |

---

## 観測レイアウト（54 次元）

`ObservationsCfg.PolicyCfg` の **宣言順** で連結されます。

| 項 | 次元 |
|----|------|
| imu_dx | 1 |
| imu_gyro | 3 |
| imu_zaxis | 3 |
| imu_height | 1 |
| left/right foot contact, dx, height | 6 |
| single_support | 1 |
| joint_pos / joint_vel / actions | 36 |
| support_side / same_side_streak / episode_progress | 3 |

---

## 実行例

```powershell
python scripts/manager_based/smoke.py --headless --num_envs 4 --steps 200
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --headless --num_envs 4096
python scripts/rsl_rl/train.py --task YuukiLab-BipedPpoWalk-v0 --num_envs 16 --visualize-robots
python scripts/eval_biped_walk.py --task YuukiLab-BipedPpoWalk-v0 --load_run <run_dir_name>
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-Play-v0 --load_run <run_dir_name>
python scripts/rsl_rl/play.py --task YuukiLab-BipedPpoWalk-v0 --num_envs 16 --visualize-robots --load_run <run_dir_name>
```

GUI で全 env のロボットメッシュを見る場合は `--visualize-robots` を付ける（`sim.use_fabric` は維持され物理も GUI も同期する）。`--disable_fabric` だけだと viewport が止まって見えることがある。

---

## 変更時の注意

- 観測次元を変えた場合は PPO 設定とネットワーク入力次元を更新する
- 報酬 ablation は `self.rewards.<term>.weight = 0.0` または `= None`
- 観測 ablation は `self.observations.policy.<term> = None`
