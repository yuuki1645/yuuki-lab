# ハイパーパラメータ（PPO）

exp_030 の既定値は `conf/ppo/default.yaml` が正本です。ここでは **調整の考え方** を述べます。

## 学習率 `lr`

| 既定 | 0.00025 |
|------|---------|

- 高すぎる … 方策が発散、KL spike  
- 低すぎる … 5000 updates では足りない  

resume 時に LR を下げる（fine-tune）は一般的な手筋です。

## Rollout `rollout_steps`

| 既定 | 512 |

1 update あたり集める **環境ステップ数**（env 1 台あたり）。  
`num_envs=8` でも **512 は固定**（512×8 にはしない）。

- 長くする … advantage の分散↓、1 update あたり時間↑  
- 短くする … 更新は速いがノイジー  

## PPO 固有

| パラメータ | 既定 | 調整の目安 |
|-----------|------|-----------|
| `clip_eps` | 0.2 | 不安定なら 0.1〜0.15 |
| `ppo_epochs` | 8 | 過学習気味なら減らす |
| `minibatch_size` | 256 | GPU メモリと相談 |
| `target_kl` | 0.02 | KL 監視で早期打切 |
| `entropy_coef` | 0.05 | 探索不足なら微増 |
| `value_coef` | 0.5 | critic 暴れなら調整 |

## 正規化・クリップ

| パラメータ | 既定 | 役割 |
|-----------|------|------|
| `reward_clip` | 20.0 | 報酬 spike 抑制 |
| `adv_clip` | 10.0 | advantage 外れ値抑制 |
| `max_grad_norm` | 0.5 | 勾配クリップ |

## 調整の順序（推奨）

1. **報酬設計**が固まってから LR  
2. 学習が動くことを **smoke** で確認  
3. 不安定なら `clip_eps` / `adv_clip` / `max_grad_norm`  
4. 遅いなら `runtime.num_envs`（[parallel-rollout.md](parallel-rollout.md)）  
5. 最後に `ppo_epochs` や `rollout_steps`  

報酬とハイパラを同時にいじらない（[foundations/07-experimental-thinking.md](../foundations/07-experimental-thinking.md)）。

## 次に読む

- [algorithms/ppo.md](../algorithms/ppo.md)
- [experiments/exp_030/hydra.md](../../experiments/exp_030_biped_ppo_walk/hydra.md)
