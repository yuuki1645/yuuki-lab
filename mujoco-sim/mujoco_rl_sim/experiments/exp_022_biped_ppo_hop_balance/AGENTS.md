# Cursor / AI エージェント向け — exp_022

## 位置づけ

- **exp_021 のコピー**（モデル・学習ハイパラ・契約 `biped_ppo_v1` は同一）
- **差分**: `data.contact` 走査を一切行わない。床接触による終了・すね step ペナルティも削除
- **stance / aerial**: `config.STANCE_IMU_Z_THRESHOLD`（IMU 高さ）のみ
- **比較ベースライン**: exp_021

## 変更時の注意

- `data.contact` / `ncon` / `mj_contactForce` を参照するコードを追加しない
- 観測 dim 8–9（foot_contact）は契約維持のため **常に -1.0**（未使用）
- exp_021 の checkpoint 転移は非推奨（報酬・終了条件が異なる）
