# 並列ロールアウト（VecEnv）

PPO は **on-policy** なのでデータは新鮮な方策で集める必要があります。  
シミュがボトルネックなら、**環境を並列化** してスループットを上げます。

## 考え方

```text
親プロセス: 方策推論 + PPO 更新
子プロセス: MuJoCo step（各 1 env）
```

exp_030 は **Subproc VecEnv**（`sim/subproc_vec_env.py`）。SB3 の `SubprocVecEnv` 相当です。

## 主要パラメータ

| 項目 | exp_030 既定 |
|------|-------------|
| `runtime.num_envs` | 8（`runtime=fast`） |
| `rollout_steps` | 512（env 数とは独立） |

## スループット指標

| 指標 | 意味 |
|------|------|
| `rollout_frac` | update 時間のうち rollout の割合（高いほど sim 支配的） |
| `steps/s` | スループット |
| `ipc_s` | 親から見た vec step の壁時計（通信＋最遅 worker 含む） |

`rollout_frac > 0.85` なら VecEnv 導入前の典型。0.65 前後まで下がれば並列化が効いています。

実験正本: [experiments/exp_030/training-parallel.md](../../experiments/exp_030_biped_ppo_walk/training-parallel.md)

## 制約

`num_envs > 1` では viewer / telemetry / warmup は無効（設計上のトレードオフ）。

## プロセス並列との違い

| 方式 | 説明 |
|------|------|
| **VecEnv** | 1 学習プロセス内で env 並列 |
| **launch_parallel.ps1** | 複数の独立 train プロセス（別 run） |
| **aws_launch.py** | クラウド上で複数 Spot インスタンス |

目的が「1 run を速く」なら VecEnv、「仮説を横並び」ならプロセス / AWS 並列です。

## 次に読む

- [algorithms/ppo.md](../algorithms/ppo.md)
- [domain-randomization.md](domain-randomization.md)
