def action_to_ctrl(action_val: float, ctrl_range) -> float:
  """[-1, 1] を actuator の ctrlrange [min, max] に線形マッピングする。"""
  a = max(-1.0, min(1.0, float(action_val)))
  lo, hi = float(ctrl_range[0]), float(ctrl_range[1])
  return lo + (a + 1.0) * 0.5 * (hi - lo)
