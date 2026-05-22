# exp_003: 2 関節脚 A2C

`exp_002_2joint_a2c` と同機能（制御 50 Hz・報酬・A2C）。実験フォルダの **コピー＋リネーム** で次実験を作りやすい構成。

## 新しい実験を作る（コピー手順）

1. `exp_003_2joint_a2c` フォルダを丸ごとコピーし、`exp_004_...` など **Python モジュール名として有効な名前** にリネームする。
2. **`runs/` はコピーしない**（チェックポイントは実験フォルダ外）。
3. **`package_meta.py` は編集不要**（フォルダ名から wandb プロジェクト・チェックポイント保存先・モジュールパスを自動決定）。
4. 仮説に応じて `config.py` / `reward.py` / `observation.py` などを編集する。
5. `README.md` の先頭タイトルと仮説メモだけ更新する。

コード内の import はすべて **相対 import**（`from . import config`）。クラス名に実験連番は入れない（`AgentA2C`, `Env2JointA2C`, `PolicyObs`）。

## 制御レート（exp_001 との差分）

| 項目 | exp_001 | exp_003（= exp_002 系） |
|------|---------|-------------------------|
| 物理 (`mj_step`) | 500 Hz | 同左 |
| ポリシー（`env.step`） | 500 Hz | **50 Hz**（`FRAME_SKIP=10`） |
| `MAX_DX_PER_STEP` | 0.05 m | **0.5 m** |
| `GAMMA` | 0.99 | **≈ 0.904**（`0.99^10`） |
| `MAX_STEPS_PER_EPISODE` | 3000 | **300** |

設計メモ: [docs/control_timing_human_rl.md](../../../../docs/control_timing_human_rl.md)

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `package_meta.py` | フォルダ名から導出するパス・モジュール名（コピー時は触らない） |
| `config.py` | 報酬・観測・A2C・学習の定数 |
| `env.py` | MuJoCo 環境 |
| `observation.py` | `PolicyObs` の組み立て |
| `reward.py` / `termination.py` / `effort.py` | MDP |
| `agent.py` | Squashed Gaussian A2C（`AgentA2C`） |
| `train.py` / `checkpoint.py` / `wandb_logging.py` | 学習・保存・ログ |
| `model/main.xml` | 実験専用モデル |
| `lib/` | 実験内ユーティリティ |

チェックポイントは **`mujoco-sim/runs/<実験フォルダ名>/run_YYYYMMDD_HHMMSS/`** に保存（git 対象外）。

## 学習（train）

`mujoco-sim` ディレクトリで:

```bash
python -m mujoco_rl_sim.experiments.exp_003_2joint_a2c.train
```

再開例:

```bash
python -m mujoco_rl_sim.experiments.exp_003_2joint_a2c.train \
  --resume runs/exp_003_2joint_a2c/run_YYYYMMDD_HHMMSS/update_005000.pt \
  --lr 1e-4 \
  --num-updates 1500
```

| オプション | 説明 |
|-----------|------|
| `--resume PATH` | 相対パスは **`runs/<実験フォルダ名>/` 基準** |
| `--lr` / `--num-updates` / `--load-optimizer` | exp_002 と同様 |

wandb プロジェクト名は `config.WANDB_PROJECT`（= フォルダ名 `exp_003_2joint_a2c`）。

## 可視化・ウォームアッププレビュー

```bash
python -m mujoco_rl_sim.experiments.exp_003_2joint_a2c.visualize
python -m mujoco_rl_sim.experiments.exp_003_2joint_a2c.visualize \
  --checkpoint runs/exp_003_2joint_a2c/run_YYYYMMDD_HHMMSS/final.pt --stochastic

python -m mujoco_rl_sim.experiments.exp_003_2joint_a2c.preview_warmup
```

## 報酬・終了・観測

exp_002 と同じ設計（前進報酬の直立条件、接触終了ペナルティ、`PolicyObs` 19 次元）。詳細は exp_002 の README または各 `*.py` の docstring を参照。

## 関連ドキュメント

- [docs/control_timing_human_rl.md](../../../../docs/control_timing_human_rl.md)
