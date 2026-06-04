# exp_028: 交互片脚歩行 PPO（exp_027 コピー）

**exp_027** と同一機能の作業用コピーです（報酬・観測・学習ループは同じ）。  
設計の源流は **exp_026** の MLP を維持した **交互片脚歩行** タスクです。

| 項目 | exp_026 | exp_028 |
|------|---------|---------|
| 前進報酬 | 飛翔中も IMU `dx`、両足 `foot_dx` 合算可 | **片足支持時のみ** |
| すり足 | 抑制なし | **`double_support_penalty`** |
| 位相 | push/landing 無効 | **push / landing / 交互着地 / 遊脚離地** |
| 観測 | 48 次元 `biped_ppo_v1` | **51 次元 `biped_walk_v1`** |

## 実行

```bash
cd exp_028_biped_ppo_walk
pip install -r requirements.txt
python train.py
python visualize.py
```

補助 CLI:

```bash
python scripts/analyze_rollout.py --checkpoint runs/.../final.pt
python scripts/preview_warmup.py
.\scripts\launch_parallel.ps1
```

契約表: `python -m contract markdown`

## ディレクトリ構成

| パス | 内容 |
|------|------|
| `train.py`, `visualize.py` | 学習・可視化の入口 |
| `config.py`, `package_meta.py`, `_paths.py` | 設定・パス |
| `sim/` | 環境・観測・報酬・終了・warmup |
| `rl/` | PPO・チェックポイント・run 設定・W&B |
| `scripts/` | ロールアウト解析・warmup プレビュー・並列学習 |
| `contract/` | 観測契約 `biped_walk_v1`・PPO ループ |
| `lib/` | ctrl・正規化・dispatch 上書き |
| `telemetry/`, `mujoco_sim_common/` | Hub・viewer 共有 |

歩行ロジックの読み方: `config.py` → `sim/episode_state.py` → `sim/reward.py` → `sim/observation.py` → `sim/env.py`

## sweep（約 50 run）

```bash
python -m mujoco_rl_sim.dispatch.coordinator.cli plan --file sweeps/walk_reward_sweep_48.yaml
```

| 探索軸 | 値 | 意図 |
|--------|-----|------|
| `double_support_penalty_scale` | 4, 8, 14 | すり足抑制の強さ |
| `alternating_landing_bonus_scale` | 0.25, 0.55 | 左右交互着地 |
| `forward_reward_scale` | 40, 55 | 前進 vs shaping のバランス |
| seed | 1–4 | 12 設定 × 4 = **48 job** |

LR は `config.LR=2.5e-4` 固定（MLP 拡大時の exp_026 既定）。

## 報酬の要点

- `forward_imu` + `forward_foot`: `single_support` かつ `upright ≥ 0.62` のときのみ
- `double_support_penalty`: 両足接地中の前進（`dx` / 足 `dx`）に比例＋ベース
- `alternating_landing_bonus`: 反対脚支持からの着地エッジ
- `flight_duration_penalty`: 両足非接地が 4 step 超（ホップ抑制）
- `progress_bonus`: 片足支持時のみ IMU +X 最高値を更新

## 観測の追加（idx 12–14）

- 左/右足 site Z（正規化）
- 片足支持フラグ（+1 / それ以外 -1）

チェックポイント: `mujoco_rl_sim/runs/exp_028_biped_ppo_walk/`
