# exp_030 — 実行・テスト・補助 CLI

## 最短実行

```bash
cd exp_030_biped_ppo_walk
pip install -r requirements.txt
python train.py
python visualize.py --checkpoint ../../runs/exp_030_biped_ppo_walk/<run>/final.pt
```

初回または環境変更時は `python -m contract validate` を推奨（[workflow.md](workflow.md) 参照）。

## テスト（pytest）

```bash
pip install pytest
python -m pytest tests/ -q -m "not slow"   # 高速のみ（Hydra / eval / 契約 / 報酬）
python -m pytest tests/ -q                 # slow 含む（MuJoCo reset・1-update 学習・Subproc）
```

slow テストには **Subproc VecEnv**（`tests/subproc_vec_env_smoke_main.py` を subprocess 実行）と **`num_envs=2` の 1-update 学習スモーク** を含む。Windows `spawn` 向けに VecEnv 単体は pytest から直接 `multiprocessing` 起動しない。

リポジトリ CI: `.github/workflows/mujoco-rl-tests.yml`（push / PR で `mujoco-sim/**` 変更時）。

## 補助 CLI

```bash
python scripts/analyze_rollout.py --checkpoint run_YYYYMMDD_HHMMSS/final.pt
python scripts/eval.py --checkpoint run_YYYYMMDD_HHMMSS/final.pt
python scripts/preview_warmup.py
.\scripts\launch_parallel.ps1          # ローカル PC 上のプロセス並列
python scripts/aws_launch.py --dry-run # AWS Spot 並列（計画確認）
```

契約表: `python -m contract markdown`

AWS 本番起動: `python scripts/aws_launch.py --confirm --upload-bootstrap`（要 `aws/aws_launch.config.toml` の `enabled=true`）。  
詳細: [aws/README.md](../../../mujoco-sim/aws/README.md)。

## 関連ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [hydra.md](hydra.md) | Hydra 設定・override・run 再現 |
| [workflow.md](workflow.md) | スモーク→本番→eval の標準手順 |
| [evaluation.md](evaluation.md) | eval v0 仕様 |
| [training-parallel.md](training-parallel.md) | VecEnv・スループット・DR |
