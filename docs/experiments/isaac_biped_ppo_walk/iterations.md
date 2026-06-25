# Isaac biped_ppo_walk — 反復改善ログ

各イテレーションは **末尾に追記** する。テンプレートは `.cursor/skills/rl-improvement-loop/iteration-log-template.md`。

## 目的

**5 m 安定歩行**: `eval_biped_walk.py` で Success rate >= 5 m **≥ 80%**（`--episodes 10` 以上）

## イテレーション一覧

| # | バージョン | run_name | Success >= 5 m | 判定 |
|---|-----------|----------|----------------|------|
| — | v24 | `v24_5m_alternating` | （eval 待ち） | 進行中 |

---

## Iteration 0 — v24_5m_alternating（2026-06-26）— ベースライン記録

> スキル導入時点の既存 run をベースラインとして記録。詳細分析は次イテレーションから本形式で追記。

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

（学習完了後に eval 結果を追記）

### 次イテレーション

（v24 eval 後に分析・仮説を記載）
