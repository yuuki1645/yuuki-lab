# exp_030 — 評価仕様

学習済みチェックポイントを **固定条件** で採点し、`eval_report.json` を出力する。  
sweep ランキング用ではなく、**1 ckpt の性能を mean ± std で把握**するのが目的。

| 項目 | v0（日常評価） |
|------|----------------|
| 仕様 ID | `biped_walk_eval_v0`（`eval/spec.py`） |
| 試行数 | **10 seed × 5 ep = 50** |
| eval_seeds | `101, 102, …, 110` |
| ポリシー | **deterministic**（`act_eval`） |
| warmup | **False**（学習と同じ） |
| エピソード長 | `MAX_STEPS_PER_EPISODE`（30 s） |

### 初期姿勢ノイズ（eval のみ・`stand` keyframe 適用後）

| 対象 | ノイズ |
|------|--------|
| ルート X/Y 位置 | **なし**（平面タスク） |
| ルートヨー | ±3° |
| 関節角 12 DOF | ±2°（`jnt_range` でクリップ） |
| ルート線速度 | 各軸 ±0.05 m/s |
| ルート角速度 | 各軸 ±0.1 rad/s |

RNG: `np.random.default_rng([eval_seed, ep_index])`（50 試行すべて別ノイズ）。  
`origin_imu_x` は **ノイズ適用後** の IMU 世界 X。

### 主指標・副指標

| 種別 | 指標 |
|------|------|
| **Primary** | `displacement_x = final_imu_x - origin_imu_x` の mean |
| 統計量 | mean, std, min, max, 95%CI（全 50 試行） |
| Secondary | `episode_length`, `truncated_rate`, `termination_breakdown`, `alternating_landing_rate`, `single_support_ratio`, `double_support_ratio` |

### 実行・出力

```bash
python scripts/eval.py --checkpoint run_YYYYMMDD_HHMMSS/final.pt
# 省略時: <checkpoint 親>/eval_report.json
python scripts/eval.py --checkpoint ... --out path/to/eval_report.json
```

| ツール | 用途 |
|--------|------|
| `scripts/eval.py` | 公式採点（統計・JSON） |
| `scripts/eval_compare.py` | 複数 run の `eval_report.json` 横断比較（表・CSV） |
| `scripts/analyze_rollout.py` | デバッグ（時系列 JSON・代表フレーム PNG） |

**学習終了後**は `train.py` が自動で `final.pt` を eval し、同 run ディレクトリに
`eval_report.json` を書き出す（スキップ: `training.post_train_eval=false`）。

v0 は **JSON のみ**（W&B / dispatch 連携は未実装）。手動再 eval は `scripts/eval.py`。

### run 横断比較（CLI）

`eval_report.json` がある run だけを拾い、主指標 `eval/displacement_x_mean` の降順で一覧する。

```bash
# 既定: runs/exp_030_biped_ppo_walk/ を走査
python scripts/eval_compare.py

# 特定 run のみ
python scripts/eval_compare.py ../../runs/exp_030_biped_ppo_walk/run_20260605_130101

# CSV 出力
python scripts/eval_compare.py --csv compare.csv
```

`eval_spec_id` が `biped_walk_eval_v0` と異なる report は `!` 列と警告で示す。
