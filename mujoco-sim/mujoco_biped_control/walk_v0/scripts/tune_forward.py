"""前進歩行パラメータの簡易 grid search（開発用）。"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _paths import install  # noqa: E402

install()

from runtime.config import load_run_config  # noqa: E402
from runtime.exp030_env import create_env, reset_env  # noqa: E402


def _tri(t: float) -> float:
  t = max(0.0, min(1.0, t))
  return 1.0 - abs(2.0 * t - 1.0)


def make_action_fn(params: dict):
  """reach / push-off 付き周期歩容。"""
  ds = max(int(params["ds"] / 0.02), 1)
  period = max(int(params["period"] / 0.02), 6)
  sh = max((period - ds) // 2, 1)

  def fn(step: int, obs) -> tuple[float, ...]:
    _ = obs
    c = step % period
    if c < ds:
      w = (c + 1) / ds
      hp, kn, ank, tor = params["hp"], params["kn"], params["ank"], params["tor"]
      v = (
        0.0,
        hp * w,
        kn * w,
        ank * w,
        0.0,
        0.0,
        hp * w,
        kn * w,
        ank * w,
        0.0,
        0.0,
        tor * w,
      )
      return v

    half = (c - ds) // sh
    t = ((c - ds) % sh) / max(sh - 1, 1)
    tr = _tri(t)
    push = max(0.0, 1.0 - t / 0.25)

    if t < 0.25:
      swing_hp = params["hp"] + params["lift_hp"] * (t / 0.25)
    elif t < 0.65:
      swing_hp = params["hp"] + params["reach_hp"]
    else:
      w2 = (t - 0.65) / 0.35
      swing_hp = params["hp"] + params["reach_hp"] * (1.0 - w2) + params["hp"] * w2

    swing_kn = params["kn"] + params["ka"] * tr
    swing_ank = params["sw_ank"] if t < 0.5 else params["ank"]
    tor = params["tor"] + params["tor_sw"]

    if half == 0:
      lhr = params["roll"]
      rhr = params["roll"] * params["rs"]
      lhp = params["hp"] + params["shp"] - params["push_hp"] * push
      lk = params["kn"] + params["skn"] - params["push_kn"] * push
      la = params["ank"] + params["sank"] - params["push_ank"] * push
      return (lhr, lhp, lk, la, 0.0, rhr, swing_hp, swing_kn, swing_ank, 0.0, 0.0, tor)

    lhr = -params["roll"] * params["rs"]
    rhr = -params["roll"]
    rhp = params["hp"] + params["shp"] - params["push_hp"] * push
    rk = params["kn"] + params["skn"] - params["push_kn"] * push
    ra = params["ank"] + params["sank"] - params["push_ank"] * push
    return (lhr, swing_hp, swing_kn, swing_ank, 0.0, rhr, rhp, rk, ra, 0.0, 0.0, tor)

  return fn


def eval_params(params: dict, *, max_steps: int, seed: int) -> dict:
  cfg = load_run_config()
  env = create_env(cfg)
  obs, _ = reset_env(env, seed=seed)
  imu0 = float(env.data.site("imu_site").xpos[0])
  fn = make_action_fn(params)
  term_reason = None
  upright = 1.0
  for step in range(max_steps):
    obs, _, terminated, info = env.step(fn(step, obs), episode_step=step)
    upright = float(info.get("upright", upright))
    if terminated:
      term_reason = info.get("termination_reason")
      break
  dx = float(env.data.site("imu_site").xpos[0]) - imu0
  return {
    "dx": dx,
    "steps": step + 1,
    "term": term_reason,
    "upright": upright,
  }


def main() -> None:
  p = argparse.ArgumentParser()
  p.add_argument("--max-steps", type=int, default=1500)
  p.add_argument("--top", type=int, default=20)
  p.add_argument("--mode", choices=("coarse", "refine"), default="refine")
  args = p.parse_args()

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

  if args.mode == "coarse":
    grid = {
      "hp": [-0.38, -0.34, -0.30],
      "reach_hp": [-0.20, -0.14, -0.08],
      "ka": [0.18, 0.24, 0.30],
      "period": [1.0, 1.2, 1.4],
      "tor": [0.10, 0.16, 0.22],
    }
  else:
    grid = {
      "hp": [-0.36, -0.34, -0.32],
      "reach_hp": [-0.16, -0.14, -0.12],
      "ka": [0.20, 0.24, 0.28],
      "period": [1.0, 1.1, 1.2, 1.3],
      "push_ank": [-0.12, -0.18, -0.22],
      "tor": [0.12, 0.14, 0.16],
    }

  keys = list(grid.keys())
  results: list[tuple[float, dict]] = []
  for combo in itertools.product(*(grid[k] for k in keys)):
    params = dict(base)
    for k, v in zip(keys, combo, strict=True):
      params[k] = v
    out = eval_params(params, max_steps=args.max_steps, seed=42)
    results.append((out["dx"], {**params, **out}))

  results.sort(key=lambda x: (-x[0], -x[1]["steps"]))
  print("total combos:", len(results))
  print("positive dx count:", sum(1 for dx, _ in results if dx > 0))
  for dx, row in results[: args.top]:
    print(
      "dx=%+.3f steps=%d term=%s hp=%.2f reach=%.2f ka=%.2f period=%.1f push_ank=%.2f tor=%.2f"
      % (
        dx,
        row["steps"],
        row["term"],
        row["hp"],
        row["reach_hp"],
        row["ka"],
        row["period"],
        row["push_ank"],
        row["tor"],
      )
    )
  if results:
    print("BEST_DX", results[0][0], "STEPS", results[0][1]["steps"])


if __name__ == "__main__":
  main()
