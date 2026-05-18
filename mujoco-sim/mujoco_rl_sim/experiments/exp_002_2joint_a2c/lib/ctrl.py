def clip_policy_action(action_val: float) -> float:
  """ポリシー出力を [-1, 1] にクリップする。"""
  return max(-1.0, min(1.0, float(action_val)))


def action_to_ctrl(action_val: float, ctrl_range) -> float:
  """[-1, 1] の action_val を actuator の ctrlrange [min, max] に線形マッピングする。

  action_val は clip_policy_action 済みであること。
  """
  lo, hi = float(ctrl_range[0]), float(ctrl_range[1])
  return lo + (float(action_val) + 1.0) * 0.5 * (hi - lo)
