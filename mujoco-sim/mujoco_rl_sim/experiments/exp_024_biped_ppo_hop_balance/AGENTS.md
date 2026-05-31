# Cursor / AI エージェント向け — exp_024

## 位置づけ

- **exp_023 の派生**（`model/main.xml` は同一・足裏 25 cm×10 cm）
- **報酬差分**（ヨーすり抜け対策）:
  1. 前後傾きペナルティ・後傾終了 → **ボディ +X への `lean_fwd_body`**（`lib/pose.py`）
  2. **ヨーずれ shaping** → `heading_align = dot(body +X, world +X)` が `HEADING_ALIGN_MIN` 未満
  3. **水平傾き shaping** → `tilt_horiz = hypot(zaxis_x, zaxis_y)`
- **契約**: `biped_ppo_v1`（観測 42 次元は exp_023 と同一）
- **比較ベースライン**: exp_023

## 変更時の注意

- 姿勢量は `lib/pose.py` に集約。`reward.py` / `termination.py` でワールド `imu_zaxis_x` だけに戻さない
- 観測次元を変える場合は `biped_v1.py` + `validate` を更新
