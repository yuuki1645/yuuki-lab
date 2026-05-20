"""ターミナル用の簡易 ASCII バー（debug.print_step_overlay）。"""


def terminal_bar(min_value: float, max_value: float, value: float) -> str:
  rate = (value - min_value) / (max_value - min_value)
  bar_length = 20
  filled_length = int(bar_length * rate)
  filled_length = max(0, min(bar_length, filled_length))
  bar = "[" + "█" * filled_length + " " * (bar_length - filled_length) + f"] ({min_value:.1f} -- {max_value:.1f})"
  if rate < 0.0:
    bar += " (<<<)"
  if rate > 1.0:
    bar += " (   >>>)"
  return bar
