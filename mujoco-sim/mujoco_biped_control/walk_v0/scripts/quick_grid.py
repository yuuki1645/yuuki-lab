"""短時間 grid search。"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _paths import install  # noqa: E402

install()

from scripts.tune_forward import eval_params  # noqa: E402

base = dict(
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
grid = {
  "reach_hp": [-0.16, -0.14, -0.12],
  "ka": [0.18, 0.24, 0.28],
  "period": [1.0, 1.1, 1.2, 1.3],
  "push_ank": [-0.12, -0.15, -0.18, -0.22],
  "tor": [0.12, 0.14, 0.16],
}
keys = list(grid.keys())
res = []
for combo in itertools.product(*(grid[k] for k in keys)):
  p = dict(base)
  for k, v in zip(keys, combo, strict=True):
    p[k] = v
  o = eval_params(p, max_steps=1500, seed=42)
  res.append((o["dx"], o["steps"], o["term"], p))
res.sort(key=lambda x: (-x[0], -x[1]))
for dx, steps, term, p in res[:10]:
  print(
    "dx=%+.3f steps=%d term=%s reach=%.2f ka=%.2f period=%.1f push_ank=%.2f tor=%.2f"
    % (
      dx,
      steps,
      term,
      p["reach_hp"],
      p["ka"],
      p["period"],
      p["push_ank"],
      p["tor"],
    )
  )
print("BEST_DX", res[0][0], "STEPS", res[0][1])
