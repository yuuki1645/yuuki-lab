# exp_024 メモ

exp_023 からの差分: 姿勢ペナルティのヨーすり抜け対策（`lib/pose.py`）。

- `lean_fwd_body` … 前後傾き・後傾終了・飛翔前傾ゲート
- `heading_align` … 正面維持 shaping（終了には使わない）
- `tilt_horiz` … 水平面傾き（横倒れ含む）
