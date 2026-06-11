"""WalkController パラメータをランダム探索して最大 displacement_x を探す。"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _paths import install  # noqa: E402

install()

import numpy as np  # noqa: E402

from controller.walk import WalkController  # noqa: E402
from runtime.config import ControlParams, load_run_config  # noqa: E402
from runtime.exp030_env import create_env, reset_env  # noqa: E402


def evaluate(params: ControlParams, *, max_steps: int, seed: int) -> dict:
  cfg = load_run_config()
  env = create_env(cfg)
  dt = float(env._ctx.cfg.sim.control_timestep_s)
  ctrl = WalkController(params)
  obs, _ = reset_env(env, seed=seed)
  x0 = float(env.data.site("imu_site").xpos[0])
  term = None
  for step in range(max_steps):
    action, _ = ctrl.compute_action(
      step=step,
      obs=np.asarray(obs),
      env=env,
      control_dt=dt,
    )
    obs, _, terminated, info = env.step(action, episode_step=step)
    if terminated:
      term = info.get("termination_reason")
      break
  dx = float(env.data.site("imu_site").xpos[0]) - x0
  return {"dx": dx, "steps": step + 1, "term": term}


def mutate(base: ControlParams, rng: random.Random, scale: float) -> ControlParams:
  d = base.__dict__.copy()

  def n(name: str, lo: float, hi: float, sigma: float) -> None:
    d[name] = float(np.clip(d[name] + rng.gauss(0.0, sigma * scale), lo, hi))

  n("cycle_period_s", 0.95, 1.55, 0.08)
  n("base_hip_pitch", -0.42, -0.28, 0.03)
  n("base_torso_pitch", 0.12, 0.24, 0.02)
  n("swing_reach_hip", -0.22, -0.10, 0.02)
  n("swing_knee_amp", 0.14, 0.28, 0.03)
  n("push_off_ankle", -0.24, -0.10, 0.03)
  n("forward_dx_gain", 2.0, 12.0, 2.0)
  n("target_dx_per_step", 0.003, 0.008, 0.001)
  return ControlParams(**d)


def main() -> None:
  rng = random.Random(42)
  base = ControlParams()
  best = evaluate(base, max_steps=1500, seed=42)
  best_params = base
  print("base", best)

  for i in range(40):
    scale = 1.0 if i < 20 else 0.5
    cand = mutate(best_params, rng, scale)
    out = evaluate(cand, max_steps=1500, seed=42)
    if out["dx"] > best["dx"]:
      best = out
      best_params = cand
      print(f"iter {i} NEW_BEST dx={out['dx']:+.3f} steps={out['steps']} term={out['term']}")
      print(" ", cand)

  print("FINAL", best)
  print("PARAMS", best_params)


if __name__ == "__main__":
  main()
