# exp_030 — 学習並列化・スループット・Domain Randomization

ワークフロー全体は [workflow.md](workflow.md)。Hydra の `runtime` preset は [hydra.md](hydra.md)。

## 学習時 Domain Randomization（v1）

| 項目 | 内容 |
|------|------|
| 対象 | 初期姿勢ノイズ（eval 同レンジ）・足底 slide friction・全 actuator kp/kv |
| タイミング | 学習 `reset(episode_index=...)` のみ（エピソードごと） |
| eval | **変更なし**（`reset_eval` + 公式 eval ノイズ） |
| 既定 | **ON**（無効化: `training.training_dr=false` または `python train.py training.training_dr=false`） |
| RNG | `training_seed` + `episode_index`（eval seed とは独立） |

`visualize.py` / `scripts/eval.py` / `analyze_rollout.py` は DR **なし**（決定的 stand）。

実装: `sim/domain_randomization.py`。

## 学習スループット

学習ログ（`LOG_EVERY` ごと）に **rollout / PPO update の壁時計** を表示する。最速設定:

```powershell
python train.py runtime=fast runtime.step_wall_sleep=0
```

（`launch_parallel.ps1` はプロセス並列。1 プロセスあたりの VecEnv は `runtime.num_envs` で指定）

### レベル1: ボトルネック計測

| 指標 | 意味 |
|------|------|
| `rollout_s` | 環境ロールアウト収集 [s]（act_batch + vec step + store 等の合計） |
| `ppo_s` | PPO 勾配更新 [s] |
| `rollout_frac` | rollout が update 全体に占める割合 |
| `steps/s` | `ROLLOUT_STEPS / rollout_s` |

`rollout_frac` の読み方:

| 目安 | 意味 |
|------|------|
| **0.85 超** | sim 側がほぼ支配的（VecEnv 導入前の典型） |
| **0.65〜0.75** | VecEnv 導入後。PPO 側の最適化も効く |
| **0.5 未満** | PPO またはその他が支配的 |

W&B には `train/rollout_fraction`・`train/act_batch_wall_s`・`train/ipc_wall_s` 等も記録（`fav/*` エイリアスあり）。

実装: `lib/train_throughput.py`。

### レベル2: Subproc VecEnv（ロールアウト物理並列）

`runtime.num_envs > 1` のとき、**子プロセスが MuJoCo `step`、親プロセスが方策推論 + PPO 更新** を担当する（SB3 `SubprocVecEnv` 相当）。子に方策モデルは載せない。子プロセスには run の `.hydra/config.yaml` パスを渡す。

```powershell
python train.py runtime=fast
python train.py runtime.num_envs=4
```

| 項目 | 内容 |
|------|------|
| 既定 | `runtime=fast` で `num_envs=8`（`conf/runtime/fast.yaml`） |
| 1 update のサンプル数 | `ROLLOUT_STEPS`（512）固定（SB3 流の 512×N にはしない） |
| 制約 | `num_envs>1` では viewer / telemetry / warmup 無効 |
| 通信 | `multiprocessing.Pipe` + pickle（軽量 `step_info`） |
| ログ（`num_envs>1`） | `num_envs`・`ipc_s` をコンソールに追加 |

**`ipc_s` とは:** 親プロセスから見た `vec_env.step()` の累積壁時計 [s]。Pipe の send/recv **と** 子プロセス内 MuJoCo 実行 **と** 最遅 worker 待ちを含む（純粋な通信オーバーヘッドだけではない）。

**参考ベンチ**（Threadripper 2950X 16C / RTX 4080 SUPER、`--step-wall-sleep 0`、10 updates 平均）:

| `num_envs` | `avg_update_s` | `avg_steps/s` | `rollout_frac` | 全体 speedup |
|------------|----------------|---------------|----------------|--------------|
| 1 | 1.685 s | 345 | 0.88 | 1.00× |
| 4 | 0.834 s | 832 | 0.74 | 2.02× |
| 8 | 0.614 s | 1280 | 0.65 | **2.74×** |

N=4→8 は逓減（update 1.36×）のため、16C マシンでは **N=8 が実用的な sweet spot**。N=12/16 は任意ベンチで頭打ち確認。

実装: `sim/subproc_vec_env.py`・`sim/step_info_ipc.py`・`rl/agent.py`（`act_batch`）・`contract/session.py`（`_collect_rollout_subproc`）。

## 学習 seed

優先順位: Hydra `training.seed` > 環境変数 `DISPATCH_SEED` > 未指定（非決定的）。

実装: `lib/training_seed.py`。
