# mujoco_rl_sim 実験 — AI エージェント向け共通メモ

## 実行方法（スタンドアロン）

各 `exp_*` フォルダは **単体で完結** しています（`contract/` 等は実験フォルダ内に同梱）。

```bash
cd experiments/<exp_name>
pip install -r requirements.txt   # 初回のみ
python train.py
python visualize.py
```

チェックポイントは `mujoco_rl_sim/runs/<exp_name>/` に保存されます（実験フォルダ外・CWD 非依存）。

## 「2joint」実験名の意味

`exp_*_2joint_*` の **2joint は膝・足首の 2 関節（DOF）** を指す。  
**脚が 2 本（両脚・バイペッド）という意味ではない。**

## ロボット形態（現行 main.xml 系）

| 項目 | 値 |
|------|-----|
| 脚の本数 | **1**（モノポッド） |
| ルート | `freejoint` 付き `basket_thigh` |
| 駆動 | 膝 + 足首サーボ |
| 典型タスク | 片脚ホッピング（exp_008 以降） |

## アクティブな実験

| 範囲 | 場所 |
|------|------|
| **exp_015 以降** | `experiments/exp_*`（本線） |
| exp_001〜014 | `experiments/archive/exp_*`（参照用・アーカイブ） |

## 実験の系統（archive: exp_001〜014）

| 実験 | タスク想定 | 備考 |
|------|------------|------|
| exp_001〜005 | 片脚・前進学習 | 歩行寄り shaping の源流 |
| exp_006 | 片脚 + 足底観測 | 歩行寄り shaping 継承 |
| exp_007a | ablation | 接地必須前進（ホッパ主線ではない） |
| **exp_008** | **片脚ホッパ** | ホップ向け shaping。`archive/exp_008/AGENTS.md` 必読 |
| exp_009 | 片脚ホッパ | exp_008 + 飛翔前傾で IMU 前進減衰・長飛翔ペナルティ・30 s エピソード |
| **exp_010** | 片脚ホッパ（10 m 目標） | exp_009 + 進捗報酬・飛翔膝過屈曲ペナルティ・足底摩擦 XML |

## 両脚と勘違いしやすいポイント

- `KNEE_HUMAN_FLEX` … 人間の**片脚**の膝曲げレンジ。両脚歩行用ではない。
- `foot_dx` + `dx` … 片脚でも足元スライド／体幹前進の区別用。
- 将来バイペッドを追加する場合は **別 XML・別実験ディレクトリ** にする（既存 exp を上書きしない）。

## エージェント作業前チェックリスト

1. `model/main.xml` に脚が何本あるか確認（現状は 1 本）
2. `config.ROBOT_MORPHOLOGY` または実験 `README.md` を読む
3. ホッパ実験では飛翔中 `dx` を殺す変更を提案しない
