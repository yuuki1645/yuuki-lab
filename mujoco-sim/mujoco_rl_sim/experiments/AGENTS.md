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

## ドキュメント運用（README + docs）

| 場所 | 役割 |
|------|------|
| `experiments/<exp_name>/README.md` | **入口**（概要・最短手順・docs へのリンク表） |
| `docs/experiments/<exp_name>/`（リポジトリルート `yuuki-lab/docs/`） | **詳細正本**（ワークフロー・報酬・終了・コードリーディング・実装） |
| `experiments/<exp_name>/AGENTS.md` | 実験固有の落とし穴・変更注意のみ（長文は docs へ） |

実験 README から docs への相対パス例: `../../../../docs/experiments/<exp_name>/`（`mujoco-sim/mujoco_rl_sim/experiments/<exp_name>/` から）

**移行状況**: **exp_030** から本運用。それ以前の exp（exp_029 等）は README 内に詳細が残っている場合がある。新規・コピー先は docs 分離を優先する。

## 新 exp 作成時 — README と docs に書くこと

新規 `exp_*` または exp コピー直後:

### 実験 README（簡略）

1. **概要** … 由来 exp・タスク・exp 間 diff 表
2. **最短手順** … `train.py` / 代表的な override
3. **詳細ドキュメント** … `docs/experiments/<exp_name>/README.md` へのリンク表
4. **AGENTS.md** へのリンク

### docs/experiments/<exp_name>/（詳細・ファイル分割推奨）

少なくとも次を **別 md に分けて** 整備する（1 ファイルに詰め込まない）:

| ファイル（例） | 内容 |
|---------------|------|
| `README.md` | 目次・コード正本への参照 |
| `quickstart.md` | 実行・pytest・補助 CLI |
| `workflow.md` | 実験ワークフロー（スモーク→本番→eval） |
| `hydra.md` | 設定・override・再現（Hydra 利用 exp） |
| `code-reading.md` | 読み順・処理フロー・変更対応表 |
| `architecture.md` | ディレクトリ構成・レイヤー |
| `reward.md` | **報酬設計の正本**（下記テンプレ） |
| `termination.md` | **終了条件の正本**（下記テンプレ） |
| `evaluation.md` | eval 仕様（あれば） |
| `sweep.md` | sweep（あれば） |

コピー元 exp の docs をベースに、**diff したファイルだけ**更新する。

### docs「報酬設計」のテンプレ（`reward.md`）

`sim/reward.py`（または相当モジュール）を読んだうえで、少なくとも次を含める:

1. **設計方針** … タスク目標（歩行 / ホップ / バランス等）と、前の exp との意図的な差分（表形式可）
2. **合成式** … 1 ステップ（または 1 制御ステップ）の `reward_total` の式。`reward.py` 内の `forward` / `shaping` / その他（`env.py` で加算する終了ペナルティ等）の境界を明示
3. **前提状態** … 報酬が依存するエピソード状態（例: 片足支持、着地エッジ、`aerial_steps`）。更新モジュール名を記載
4. **ゲート条件** … 「いつ主報酬が 0 になるか」（例: `forward_allowed`、接地必須、片足支持必須）
5. **項の一覧表** … 各項について **名前・発火条件・数式（係数は config 名で）・実装ファイル** を表で列挙。ボーナスとペナルティを分ける
6. **config との対応** … 主要係数が `config.py` のどの定数か（全文コピーは不要、名前と既定値でよい）
7. **ログキー** … W&B / Hub / `step_info` で追うキー名（契約 `RewardLogSpec` があれば参照）
8. **sweep 対象** … `dispatch_config` や YAML で上書きされる係数があれば列挙

観測だけ変えて報酬が同じ exp をコピーした場合も、「変更なし（コピー元と同一）」と明記する。  
報酬を変えたのに `reward.md` が古いまま、は **作業未完了** とみなす。

### docs「終了条件と終了ペナルティ」のテンプレ（`termination.md`）

`sim/termination.py`（または相当モジュール）と `sim/env.py` の合成を読んだうえで、少なくとも次を含める:

1. **実装の正本** … `termination.py` / `env.py` / truncation を付けるモジュール（例: `contract/session.py`）への参照
2. **用語** … `terminated` / `truncated` / `termination_reason` の区別
3. **評価タイミング** … 物理ステップ vs 制御ステップ、接触終了と姿勢終了の優先順
4. **終了理由一覧表** … 各 reason について **発火条件・ペナルティ・実装関数・config 依存** を列挙
5. **閾値と測定信号** … 使う site / sensor / 内部指標、単位、config 定数との対応
6. **ペナルティの式** … 固定値ペナルティと力依存ペナルティを分けて記載（係数表）
7. **終了しないペナルティ** … ステップごと積算される接触ペナルティ等があれば明記
8. **報酬合成への影響** … `reward_total` への加算タイミング（`REWARD_ENABLE_*` との関係）
9. **ログキー** … `step_info` / W&B / Hub で追うキー名
10. **変更ガイド** … 「変えたい内容 → 触るファイル」対応表

終了条件がコピー元と同一の exp でも、「変更なし（コピー元と同一）」と明記する。  
終了条件を変えたのに `termination.md` が古いまま、は **作業未完了** とみなす。
