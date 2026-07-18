# アーカイブ済み実験（exp_001〜exp_014）

終了した早期実験のコードスナップショット。  
MuJoCo 内の後継系統は `experiments/exp_015_*` 以降（最終は exp_030）。**リポジトリ全体の RL 本線は `isaac-lab/`**。

チェックポイントは `mujoco_rl_sim/runs/archive/<実験名>/` にあります。

## 実行

```bash
cd mujoco-sim/mujoco_rl_sim/experiments/archive/<exp_name>
python train.py
```

`package_meta.py` の `CHECKPOINT_ROOT` は `mujoco_rl_sim/runs/archive/<EXP_NAME>/` を指します。
