"""107 step 以降の生存 + dx 最大化探索。"""
import sys
sys.path.insert(0, ".")
from _paths import install
install()
from dataclasses import replace
import numpy as np
from controller.walk import WalkController
from runtime.config import load_control_params, load_run_config
from runtime.exp030_env import create_env, reset_env

def run(p, max_steps=1500, seed=42):
  cfg = load_run_config()
  env = create_env(cfg)
  dt = float(env._ctx.cfg.sim.control_timestep_s)
  c = WalkController(p)
  obs, _ = reset_env(env, seed=seed)
  x0 = float(env.data.site("imu_site").xpos[0])
  for s in range(max_steps):
    a, _ = c.compute_action(step=s, obs=np.asarray(obs), env=env, control_dt=dt)
    obs, _, term, info = env.step(a, episode_step=s)
    if term:
      return float(env.data.site("imu_site").xpos[0]) - x0, s + 1, info.get("termination_reason")
  return float(env.data.site("imu_site").xpos[0]) - x0, max_steps, None

base = load_control_params()
base = replace(
  base,
  balance_ankle_gain=1.0,
  balance_torso_tilt_gain=0.6,
  balance_upright_gain=0.4,
  balance_tilt_deadband=0.0,
  balance_upright_activate=0.0,
  foot_place_gain=0.0,
)

best = {"dx": -1.0}
for hg in [0.15, 0.22, 0.30, 0.40]:
  for reach in [-0.10, -0.12, -0.14]:
    for ka in [0.16, 0.18, 0.20]:
      for ak in [0.8, 1.0, 1.2]:
        p = replace(base, balance_height_gain=hg, swing_reach_hip=reach, swing_knee_amp=ka, balance_ankle_gain=ak)
        dx, st, term = run(p)
        if dx > best["dx"]:
          best = {"dx": dx, "steps": st, "term": term, "hg": hg, "reach": reach, "ka": ka, "ak": ak}
          print("NEW", best)

print("FINAL", best)
