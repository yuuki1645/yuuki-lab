# アーカイブ済み実験（exp_001〜exp_014）

終了した早期実験のコードスナップショット。日常の学習・開発の本線は `experiments/exp_015_*` 以降。

チェックポイントは `mujoco_rl_sim/runs/archive/<実験名>/` にあります。

## 実行

```bash
cd mujoco-sim/mujoco_rl_sim/experiments/archive/<exp_name>
python train.py
```

`package_meta.py` の `CHECKPOINT_ROOT` は `mujoco_rl_sim/runs/archive/<EXP_NAME>/` を指します。
