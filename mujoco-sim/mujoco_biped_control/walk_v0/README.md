# walk_v0 — 明示制御による両脚歩行

RL ではなく **制御プログラム** で exp_030 と同じ MuJoCo モデルを動かす実験です。  
制御アルゴリズムの詳細は **意図的に固定していません**。改善は `controller/walk.py` と `conf/controller.yaml` を AI / 人間が編集する想定です。

## ファイル

| ファイル | 役割 |
|---------|------|
| `controller/walk.py` | **制御の本体**（編集対象） |
| `conf/controller.yaml` | チューニング可能な係数 |
| `conf/default.yaml` | seed・max_steps・ログ設定 |
| `run.py` | ヘッドレス走行 + ログ |
| `visualize.py` | ビューア付き走行 |
| `replay_incident.py` | インシデント瞬間の再現 |

## 出力（1 run あたり）

| ファイル | 内容 |
|---------|------|
| `run_manifest.json` | seed・設定パス（再現用） |
| `effective_run.yaml` | 実行時設定のコピー |
| `effective_controller.yaml` | 制御パラメータのコピー |
| `trajectory.jsonl` / `trajectory.csv` | 各ステップの action・IMU・接触 |
| `incidents.json` | 問題と判断した瞬間の一覧 |
| `incidents/step_XXXXX/state.npz` | その瞬間の qpos/qvel（再現用） |
| `incidents/step_XXXXX/frame.png` | オフスクリーン画像（AI 視覚理解用） |
| `summary.json` | `displacement_x`・終了理由など |

## インシデント検出

`conf/default.yaml` の `incident:` で閾値を変更できます。

- 転倒・異常接触（`terminated:*`）
- 低 upright / 低 IMU 高度
- 長時間両足非接地
- 後退・停滞（`imu_dx`）

## 再現

```bash
# 同一 seed（default.yaml の seed: 42）
python run.py

# 記録済み瞬間を viewer で確認
python replay_incident.py --run-dir <run_dir> --incident-index 0
```

## exp_030 との関係

| 項目 | walk_v0 | exp_030 |
|------|---------|---------|
| モデル | exp_030 `model/main.xml` | 同左 |
| 学習 | なし | PPO |
| 制御 | `controller/walk.py` | 方策 MLP |
| 成果物 | `runs/mujoco_biped_control/` | `runs/exp_030_biped_ppo_walk/` |
