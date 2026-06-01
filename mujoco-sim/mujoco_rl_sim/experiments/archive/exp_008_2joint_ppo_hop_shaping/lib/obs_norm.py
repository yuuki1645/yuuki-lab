"""観測の正規化ヘルパ（ポリシー入力をおおよそ [-1, 1] に揃える）。"""


def clip_scale(value: float, scale: float) -> float:
  """value / scale を [-1, 1] にクリップ。"""
  if scale <= 0.0:
    return 0.0
  return max(-1.0, min(1.0, float(value) / scale))


def range_to_norm(value: float, lo: float, hi: float) -> float:
  """関節角など [lo, hi] を [-1, 1] に線形マップ。"""
  if hi <= lo:
    return 0.0
  t = (float(value) - lo) / (hi - lo)
  return max(-1.0, min(1.0, 2.0 * t - 1.0))


def height_to_norm(z: float, z_min: float, z_max: float) -> float:
  """高さ [z_min, z_max] を [-1, 1] に線形マップ。"""
  span = z_max - z_min
  if span <= 0.0:
    return 0.0
  t = (float(z) - z_min) / span
  return max(-1.0, min(1.0, 2.0 * t - 1.0))
