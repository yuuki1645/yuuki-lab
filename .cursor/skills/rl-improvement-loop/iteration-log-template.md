# イテレーション記録テンプレート

`docs/experiments/isaac_biped_ppo_walk/iterations.md`（または対象実験の反復ログ）に **1 イテレーション = 1 節** として追記する。

---

## Iteration N — vNN_<slug>（YYYY-MM-DD）

### メタデータ

| 項目 | 値 |
|------|-----|
| 目的 | （例: 5 m 安定歩行、Success rate >= 80%） |
| ベースライン run | `2026-06-25_19-19-36_v23_5m_antipivot` |
| 今回 run | `2026-06-26_05-49-03_v24_5m_alternating` |
| チェックポイント | `model_2400.pt` |
| ブランチ | `exp/biped-walk-5m-stable` |

### 1. 前回結果の分析

**データソース**: W&B run `jds5gnid` / TB / `params/env.yaml`

| 指標 | 前回値 | 所見 |
|------|--------|------|
| `episode_displacement_x` (mean) | 1.5 m | 5 m 手前でプラトー |
| `single_support_ratio` | 0.42 | やや低い |
| `alternating_landing_ratio` | 0.31 | 交互歩行不足 |
| `mean_episode_length` | 420 step | 早期転倒多い |
| Success rate >= 5 m (eval) | 8% | 目標 80% 未達 |

**観察（事実）**:
- （ログ・eval から読み取れる事実のみ）

**解釈（仮説）**:
- （なぜそうなっているかの因果推論）

### 2. 改善判断（実装前）

| 項目 | 内容 |
|------|------|
| **仮説** | 1 文で |
| **提案変更** | ファイル + パラメータ + 変更内容 |
| **期待効果** | どの指標がどう変わるか |
| **リスク** | 想定される悪化 |

### 3. 実際の変更

| ファイル | 変更内容 | 根拠 |
|----------|----------|------|
| `biped_ppo_walk_env_cfg.py` | `enable_forward_vel=True`, 右ピボット遮断 | 前進速度報酬でプラトー突破を狙う |

```diff
# 必要なら主要 diff を短く引用
```

**スモーク結果**: `--num_envs 64 --max_iterations 5` — OK / No-Go（理由）

### 4. 学習・評価結果

**学習**:
- コマンド: `python scripts/rsl_rl/train.py ...`
- イテレーション: 600（resume from v23）
- 所要時間: ~2 h

**eval** (`eval_biped_walk.py --episodes 10`):

| 指標 | 今回 | 前回比 |
|------|------|--------|
| Mean displacement +X | 2.8 m | +1.3 m |
| Success rate >= 5 m | 22% | +14 pp |
| Success rate >= 15 m | 0% | — |
| single_support_ratio | 0.48 | +0.06 |

**W&B ハイライト**:
- `Train/mean_reward`: ...
- `Metrics/mean_milestone_level`: ...

### 5. 判定

| 項目 | 結果 |
|------|------|
| スモーク Go/No-Go | Go |
| 本番 Go/No-Go | Go（改善傾向だが目標未達） |
| **目的達成** | **未達** — Success rate 22% < 80% |

### 6. 次イテレーション

- **次の仮説**: （1 つに絞る）
- **優先度**: 高 / 中
- **メモ**: play.py で可視確認した挙動など

---

## 目的達成時の最終サマリー（ループ終了時のみ）

### Goal Achieved — YYYY-MM-DD

| 項目 | 値 |
|------|-----|
| 達成 run | |
| Success rate >= 5 m | |
| 総イテレーション数 | |
| 開始〜達成 | v22 → vNN |

**有効だった変更の要約**:
1. ...
2. ...

**残課題**（任意）:
- ...
