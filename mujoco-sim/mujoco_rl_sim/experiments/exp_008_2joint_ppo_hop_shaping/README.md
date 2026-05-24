# exp_008: 片脚ホッパ PPO + ホップ向け shaping

## ロボット形態（必読）

| 用語 | このリポジトリでの意味 |
|------|------------------------|
| **片脚 / モノポッド** | 物理的に脚は **1 本**（`basket_thigh` → 大腿 → 下腿 → 足底） |
| **2joint** | 膝・足首の **2 自由度**。脚が 2 本ある意味 **ではない** |
| **両脚 / バイペッド** | **該当しない**。歩行用 shaping は exp_006 系から削除・変更済み |

タスク: **ホッピング**（立脚 → 押し出し → 飛翔で IMU 前進 → 足底着地）。

`config.ROBOT_MORPHOLOGY = "monoped_single_leg_hopper"`

## exp_006 からの主な変更

| 項目 | exp_006 | exp_008 |
|------|---------|---------|
| 膝屈曲ボーナス | あり（歩行向け） | **なし** |
| 直立ボーナス | 常時 | **飛翔中のみ**（`dx≥0`） |
| 前進 `foot_dx` | 常時 | **接地時のみ** |
| 前傾ペナルティ | なし | **長い飛翔＋前傾** |
| 低姿勢ペナルティ | 常時 | 立脚は緩和、飛翔は墜落寄り |
| `contact_shank` | 即終了 | **ステップペナルティ**（継続） |
| 押し出し・着地 | なし | **小ボーナス** |
| 姿勢 `MIN_IMU_Z` | 固定 | 立脚中は緩和 |

観測（25 次元）・PPO ハイパーパラメータ・XML ジオメトリは exp_006 と同一。

## 学習

`mujoco-sim` ディレクトリで:

```bash
python -m mujoco_rl_sim.experiments.exp_008_2joint_ppo_hop_shaping.train
```

チェックポイント: `mujoco_rl_sim/runs/exp_008_2joint_ppo_hop_shaping/run_YYYYMMDD_HHMMSS/`

## ロールアウト分析

```bash
python -m mujoco_rl_sim.experiments.exp_008_2joint_ppo_hop_shaping.analyze_rollout \
  --checkpoint run_YYYYMMDD_HHMMSS/latest.pt --seed 42
```

## 比較ベースライン

- `exp_006_2joint_ppo_shaping` … 歩行寄り shaping + 空中前進許容
- `exp_007a_2joint_ppo_shaping` … 接地必須前進（ホッパには不適、参考用）

## AI エージェント向け

`AGENTS.md`（本ディレクトリ）と `mujoco_rl_sim/experiments/AGENTS.md` を参照。
