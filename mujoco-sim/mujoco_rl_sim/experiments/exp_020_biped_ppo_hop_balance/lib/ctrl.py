"""ポリシー出力と MuJoCo ctrl の変換。"""

import numpy as np


def clip_policy_action(action_val: float) -> float:
  """ポリシー出力を [-1, 1] にクリップする。"""
  return float(np.clip(float(action_val), -1.0, 1.0))


def action_to_ctrl(action_val: float, ctrl_range, *, neutral_ctrl: float) -> float:
  """[-1, 1] の action を ctrl に写す。action=0 は neutral_ctrl（立位など）。

  action=-1 → ctrlrange 下限、action=+1 → 上限。非対称 ctrlrange（膝 0〜屈曲など）でも
  立位 keyframe の関節角を中立にできる。
  """
  lo, hi = float(ctrl_range[0]), float(ctrl_range[1])
  neutral = float(np.clip(float(neutral_ctrl), lo, hi))
  a = clip_policy_action(action_val)
  if a >= 0.0:
    return neutral + a * (hi - neutral)
  return neutral + a * (neutral - lo)


def ctrl_to_action(ctrl: float, ctrl_range, *, neutral_ctrl: float) -> float:
  """action_to_ctrl の逆（warmup 用）。"""
  lo, hi = float(ctrl_range[0]), float(ctrl_range[1])
  neutral = float(np.clip(float(neutral_ctrl), lo, hi))
  c = float(np.clip(float(ctrl), lo, hi))
  if c >= neutral:
    span = hi - neutral
    if span <= 0.0:
      return 0.0
    return (c - neutral) / span
  span = neutral - lo
  if span <= 0.0:
    return 0.0
  return (c - neutral) / span
