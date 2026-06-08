# contract（exp_030 同梱）

Hub テレメトリ（`biped_walk_v1`・**51 次元**）と PPO 学習ループの **契約正本**（本実験フォルダ内 `contract/`）。

exp_029 と同様。`contract/__init__.py` の `TELEMETRY_CONTRACT = BIPED_WALK_V1`。

追加モジュール:
- `__init__.py（TELEMETRY_CONTRACT）`
- `biped_v1.py（レガシー・未使用）`

## 使い方（本フォルダで）

```bash
python -m contract validate
python -m contract markdown
python -m contract markdown --reward
python train.py
```

## 参照実験

| 実験 | 契約の使い方 |
|------|----------------|
| exp_030 | `contract.TELEMETRY_CONTRACT` + `contract.session.run_ppo_train` |

## モジュール

| ファイル | 役割 |
|----------|------|
| `biped_walk_v1.py` | **契約定義（51 次元・正本）** |
| `spec.py` | `TelemetryContract`, `ObservationSlice` 等 |
| `telemetry.py` | reset/step ペイロード組み立て |
| `session.py` | PPO 学習ループ共通化 |
| `validate.py` | 観測ベクトル次元・有限値チェック |
| `codegen.py` | README 用 Markdown 生成 |
| `__main__.py` | `validate` / `markdown` CLI |
