# Cursor / AI エージェント向け — exp_018

## ロボット形態

| 項目 | 値 |
|------|-----|
| 目標 | **両脚バイペッド**（[robot_front.jpg](../../../../docs/images/robot_front.jpg) 参照） |
| XML | `model/main.xml` — 10 DOF 両脚（robot_spec + 設計図寸法） |
| 系統 | exp_017（片脚ホッパ）から fork。報酬・観測は暫定コピー |

## exp_017 からの意図

- **片脚ホッパではなく両脚歩行/バランス**が最終目標
- 当面は exp_017 と同じ報酬係数・PPO 設定
- XML 差し替え後に `OBS_DIM` / `ACTION_DIM` / 接触・観測・報酬を両脚向けに更新する

## 変更時の注意

| やらないこと | 理由 |
|--------------|------|
| 片脚前提の `knee`/`ankle` 関節名をコード側で放置 | XML は `left_knee_pitch` 等 — 観測・actuator 要更新 |
| 片脚ホッパ前提の geom 名を XML なしで変更 | XML 確定後に合わせる |
| exp_017 の ckpt をそのまま転移 | 形態が異なる（両脚 XML 確定後に再検討） |

## 評価

両脚 XML 確定後、`analyze_rollout --seed 42`（30 s）で前進距離・転倒率を確認。
