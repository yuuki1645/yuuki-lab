"""少数パラメータを 1500 step 評価。"""

from __future__ import annotations

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

candidates = [
  ("aggressive", {**base, "reach_hp": -0.14, "ka": 0.24, "period": 1.1, "push_ank": -0.18}),
  ("medium", {**base, "reach_hp": -0.12, "ka": 0.18, "period": 1.2, "push_ank": -0.15}),
  ("slow", {**base, "reach_hp": -0.10, "ka": 0.16, "period": 1.4, "push_ank": -0.12}),
  ("slow2", {**base, "reach_hp": -0.08, "ka": 0.14, "period": 1.5, "push_ank": -0.10, "tor": 0.16}),
  ("fast_small", {**base, "reach_hp": -0.10, "ka": 0.20, "period": 0.9, "push_ank": -0.14}),
]

for name, p in candidates:
  o = eval_params(p, max_steps=1500, seed=42)
  print(name, o)
