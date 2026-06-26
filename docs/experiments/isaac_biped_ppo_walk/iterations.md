# Isaac biped_ppo_walk — 反復改善ログ

各イテレーションは **末尾に追記** する。テンプレートは `.cursor/skills/rl-improvement-loop/iteration-log-template.md`。

## 目的

**5 m 安定歩行**: `eval_biped_walk.py` で Success rate >= 5 m **≥ 80%**（`--episodes 10` 以上）

## イテレーション一覧

| # | バージョン | run_name | Success >= 5 m | 判定 |
|---|-----------|----------|----------------|------|
| 0 | v24 | `v24_5m_alternating` | 0.0% | No-Go（v23 より悪化） |
| 1 | v25 | `v25_5m_longhorizon` | 0.0% | Go（微改善、目標未達） |

---

## Iteration 0 — v24_5m_alternating（2026-06-26）

### メタデータ

| 項目 | 値 |
|------|-----|
| 目的 | 5 m 安定歩行（Success rate >= 80%） |
| ベースライン run | `2026-06-25_19-19-36_v23_5m_antipivot` / `model_2400.pt` |
| 今回 run | `2026-06-26_05-49-03_v24_5m_alternating` |
| チェックポイント | `model_2800.pt`（iter 2914 で中断、model_3000 なし） |
| W&B | `jds5gnid` |

### 1. 前回結果の分析（v23）

**データソース**: W&B `88qx9zwi` / eval `model_2400.pt`

| 指標 | v23 値 | 所見 |
|------|--------|------|
| `episode_displacement_x` (train) | 1.23 m | ~1.5 m プラトー |
| `single_support_ratio` | 0.49 | 許容範囲 |
| `alternating_landing_ratio` | 0.007 | 交互歩行ほぼ未学習 |
| `mean_episode_length` | 158 step | 5 m 到達には不足 |
| Success rate >= 5 m (eval) | 0% | mean 1.48 m, max 2.84 m |

**観察**: 右ピボット寄り（`right_contact_ratio` ~0.47）だが前進は安定。交互着地率が極端に低く、2〜3 m で頭打ち。

**仮説（v24）**: 右ピボット時の前進遮断・左支持のみ足前進・歩行速度強化で交互歩行を強制し 5 m を狙う。

### 2. 改善判断（v24 実装前）

| 項目 | 内容 |
|------|------|
| **仮説** | 右ピボット degenerate gait を遮断すれば交互歩行が増え、5 m に到達できる |
| **提案変更** | `forward_block_right_pivot_streak=2`, `forward_foot_left_stance_only=True`, `forward_vel` 強化, `alternating_landing` 強化 |
| **期待効果** | `alternating_landing_ratio`↑, `episode_displacement_x` → 5 m |
| **リスク** | fine-tune 中の報酬分布急変でポリシー崩壊 |

### 3. 実際の変更（v24）

`biped_ppo_walk_env_cfg.py` / `mdp/reward.py` に v24 パラメータを反映（右ピボット遮断・左足前進限定・速度報酬強化）。

**スモーク**: 実施済み（当時 Go）

### 4. 学習・評価結果

**学習**: v23 `model_2400.pt` から resume、600 iter 予定 → iter 2914 で停止（`model_2800.pt` が最新）

**W&B ハイライト（v23 → v24 終盤）**:

| 指標 | v23 | v24 @2800 | 変化 |
|------|-----|-----------|------|
| `episode_displacement_x` | 1.23 m | 0.90 m | **悪化** |
| `single_support_ratio` | 0.49 | 0.37 | 悪化 |
| `alternating_landing_ratio` | 0.007 | 0.024 | 微改善 |
| `mean_milestone_level` | 0.39 | 0.14 | 悪化 |
| `Train/mean_reward` | -245 | -429 | 悪化 |

step 2550 付近で displacement が 1.1 m → 0.7 m に急落（fine-tune 崩壊）。

**eval** (`model_2800.pt`, 640 ep, 64 env):

| 指標 | v24 | v23 (比較) |
|------|-----|------------|
| Mean displacement +X | 0.93 m | 1.48 m |
| Max displacement +X | 1.15 m | 2.84 m |
| Success rate >= 5 m | 0.0% | 0.0% |
| single_support_ratio | 0.35 | 0.51 |

### 5. 判定

| 項目 | 結果 |
|------|------|
| 本番 Go/No-Go | **No-Go** — v23 より全面悪化 |
| **目的達成** | **未達** |

### 6. 次イテレーション（v25）

- **次の仮説**: v24 の強制遮断は fine-tune を破壊する。v23 ベースに戻し、**長寿命ボーナス（`long_horizon_bonus_scale`）のみ**強化してエピソード長延伸→累積 5 m を狙う。
- **優先度**: 高

---

## Iteration 1 — v25_5m_longhorizon（2026-06-26）— 実装・学習

### 2. 改善判断（実装前）

| 項目 | 内容 |
|------|------|
| **仮説** | ep ~160 step で転倒するため 5 m に届かない。長寿命 shaping を強めると生存 step が伸び、同じ歩幅でも 5 m に到達できる |
| **提案変更** | `long_horizon_bonus_scale`: 1.00 → 1.40（**1 軸のみ**）。v24 固有変更はすべて v23 値へ戻す |
| **期待効果** | `mean_episode_length`↑, `episode_displacement_x` 2 m → 3 m+ |
| **リスク** | 立ち止まりハック（alive bonus とのバランス） |

### 3. 実際の変更

| ファイル | 変更内容 | 根拠 |
|----------|----------|------|
| `biped_ppo_walk_env_cfg.py` | v24 固有変更を v23 値へ戻す + `long_horizon_bonus_scale` 1.00→1.40 | v24 No-Go 後の 1 軸仮説 |
| `biped_ppo_walk_env.py` | `last_episode_displacement` 追加 | eval 計測修正 |
| `eval_biped_walk.py` | ログパス絶対化・エピソード集計修正 | eval 信頼性向上 |

**スモーク結果**: `v25_smoke_longhorizon` 5 iter — **Go**（クラッシュなし、iter 4 で ep length 101 回復）

### 4. 学習・評価結果

**学習**: `2026-06-26_08-14-43_v25_5m_longhorizon`、iter 2999、`model_2999.pt`、所要 ~78 min

**eval** (`model_2999.pt`, 640 ep):

| 指標 | v25 | v23 比 |
|------|-----|--------|
| Mean displacement +X | 1.51 m | +0.03 m |
| Max displacement +X | 3.41 m | +0.57 m |
| Success rate >= 5 m | 0.0% | — |
| single_support_ratio | 0.50 | -0.01 |

**W&B 終盤**: `episode_displacement_x` 1.23 m、`mean_episode_length` 170 step（v23: 158）

### 5. 判定

| 項目 | 結果 |
|------|------|
| スモーク Go/No-Go | Go |
| 本番 Go/No-Go | **Go**（v23 比微改善、崩壊なし） |
| **目的達成** | **未達** — Success 0% < 80% |

### 6. 次イテレーション（v26）

- **次の仮説**: 長寿命ボーナスだけでは 5 m に不足。`displacement_milestone_scales` の 5 m ティア（index 2）を 35→55 に強化し、到達インセンティブを上げる（1 軸）
- **ベース**: v25 `model_2999.pt`

---

## Iteration 0 — v24_5m_alternating（2026-06-26）— ベースライン記録（旧メモ）

> 以下はスキル導入時の簡易メモ。詳細は上記 Iteration 0 節を参照。

### メタデータ

| 項目 | 値 |
|------|-----|
| 目的 | 5 m 安定歩行（Success rate >= 80%） |
| run | `2026-06-26_05-49-03_v24_5m_alternating` |
| ベース | `2026-06-25_19-19-36_v23_5m_antipivot` / `model_2400.pt` |
| 設定バージョン | v24（右ピボット遮断・左支持足前進・forward_vel 強化） |

### 変更意図（v24）

v23 で ~1.5 m プラトー。右ピボット時の前進遮断、左支持のみ足前進、歩行速度報酬で 5 m を狙う。

### 結果サマリー

eval: Success 0%, mean disp 0.93 m（v23: 1.48 m）。No-Go。

### 次イテレーション

v25: v23 復帰 + long_horizon_bonus 強化。
