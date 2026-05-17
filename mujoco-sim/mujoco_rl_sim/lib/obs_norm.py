def clip_scale(value: float, scale: float) -> float:
  if scale <= 0.0:
    return 0.0
  return max(-1.0, min(1.0, float(value) / scale))


def range_to_norm(value: float, lo: float, hi: float) -> float:
  if hi <= lo:
    return 0.0
  t = (float(value) - lo) / (hi - lo)
  return max(-1.0, min(1.0, 2.0 * t - 1.0))


def height_to_norm(z: float, z_min: float, z_max: float) -> float:
  span = z_max - z_min
  if span <= 0.0:
    return 0.0
  t = (float(z) - z_min) / span
  return max(-1.0, min(1.0, 2.0 * t - 1.0))
