"""前進歩行の局所探索（少数コンボ・高速）。"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _paths import install  # noqa: E402

install()

from scripts.tune_forward import eval_params  # noqa: E402

BASE = dict(
  hp=-0.34,
  kn=0.05,
  ank=-0.12,
  tor=0.14,
  ds=0.06,
  period=1.2,
  roll=0.07,
  rs=0.7,
  shp=-0.03,
  skn=-0.02,
  sank=-0.08,
  push_hp=0.06,
  push_kn=-0.04,
  push_ank=-0.15,
  lift_hp=0.05,
  reach_hp=-0.14,
  ka=0.24,
  sw_ank=0.08,
  tor_sw=0.04,
)

GRID = {
  "reach_hp": [-0.15, -0.14, -0.13],
  "ka": [0.20, 0.22, 0.24],
  "period": [1.1, 1.2, 1.3],
  "push_ank": [-0.14, -0.18],
  "tor": [0.13, 0.14, 0.15],
  "kn": [0.04, 0.05, 0.06],
  "tor_sw": [0.02, 0.04, 0.06],
}

if __name__ == "__main__":
  keys = list(GRID.keys())
  results = []
  for combo in itertools.product(*(GRID[k] for k in keys)):
    params = dict(BASE)
    for k, v in zip(keys, combo, strict=True):
      params[k] = v
    out = eval_params(params, max_steps=1500, seed=42)
    results.append((out["dx"], out["steps"], out["term"], params))

  results.sort(key=lambda x: (-x[0], -x[1]))
  print("top 15:")
  for dx, steps, term, params in results[:15]:
    print(
      "dx=%+.3f steps=%d term=%s reach=%.2f ka=%.2f period=%.1f "
      "push_ank=%.2f tor=%.2f kn=%.2f tor_sw=%.2f"
      % (
        dx,
        steps,
        term,
        params["reach_hp"],
        params["ka"],
        params["period"],
        params["push_ank"],
        params["tor"],
        params["kn"],
        params["tor_sw"],
      )
    )
  print("BEST", results[0])
