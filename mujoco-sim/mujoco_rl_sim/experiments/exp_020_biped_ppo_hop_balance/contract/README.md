# mujoco_rl_sim.contract

観測ベクトル・Hub テレメトリ（`biped_ppo_v1`）・PPO 学習ループの **契約を 1 か所で定義** する内部パッケージです。

## 使い方

```bash
# 契約の自己検証
python -m mujoco_rl_sim.contract validate

# 観測 idx 表（Markdown）
python -m mujoco_rl_sim.contract markdown

# 学習（contract 駆動の実験）
python -m mujoco_rl_sim.experiments.exp_020_biped_ppo_hop_balance.train
```

## 参照実験

| 実験 | 契約の使い方 |
|------|----------------|
| exp_019 | `telemetry/biped_ppo.py` が本契約のラッパ（後方互換） |
| exp_020 | `experiment_contract.py` + `contract.session.run_ppo_train` |

## モジュール

| ファイル | 役割 |
|----------|------|
| `biped_v1.py` | `BIPED_PPO_V1` 契約定義（42 次元） |
| `telemetry.py` | reset/step ペイロード組み立て |
| `session.py` | PPO 学習ループ共通化 |
| `validate.py` | 観測ベクトル次元チェック |
| `codegen.py` | README 用 Markdown 生成 |
