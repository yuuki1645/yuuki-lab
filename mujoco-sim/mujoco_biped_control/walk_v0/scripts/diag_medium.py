"""medium 歩容の時系列診断。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _paths import install  # noqa: E402

install()

import numpy as np  # noqa: E402

from runtime.config import load_run_config  # noqa: E402
from runtime.exp030_env import create_env, reset_env  # noqa: E402
from scripts.tune_forward import make_action_fn  # noqa: E402

params = dict(
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
  reach_hp=-0.12,
  ka=0.18,
  sw_ank=0.08,
  tor_sw=0.04,
)

cfg = load_run_config()
env = create_env(cfg)
fn = make_action_fn(params)
obs, _ = reset_env(env, seed=42)
x0 = float(env.data.site("imu_site").xpos[0])
for step in range(120):
  obs, _, term, info = env.step(fn(step, obs), episode_step=step)
  o = np.asarray(obs)
  if step % 10 == 0 or term:
    print(
      "s=%d dx=%.4f x=%+.3f upright=%.3f obs6=%.3f tilt_x=%+.3f term=%s"
      % (
        step,
        float(o[0]) * 0.05,
        float(env.data.site("imu_site").xpos[0]) - x0,
        float(info.get("upright", 0)),
        float(o[6]),
        float(o[4]),
        info.get("termination_reason"),
      )
    )
  if term:
    break
