"""period=1.0 / reach=-0.10 付近の精密探索。"""
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

bal = replace(
  load_control_params(),
  balance_ankle_gain=1.0,
  balance_torso_tilt_gain=0.6,
  balance_upright_gain=0.4,
  balance_tilt_deadband=0.0,
  balance_upright_activate=0.0,
  foot_place_gain=0.0,
  balance_height_gain=0.18,
  swing_reach_hip=-0.10,
  cycle_period_s=1.0,
)

best = {"dx": -1.0}
for period in [0.95, 0.98, 1.0, 1.02, 1.05]:
  for reach in [-0.095, -0.10, -0.105, -0.11]:
    for ka in [0.16, 0.17, 0.18, 0.19]:
      for ak in [0.9, 1.0, 1.1]:
        for hk in [0.3, 0.4, 0.5]:
          p = replace(
            bal,
            cycle_period_s=period,
            swing_reach_hip=reach,
            swing_knee_amp=ka,
            balance_ankle_gain=ak,
            balance_upright_gain=hk,
          )
          dx, st, term = run(p)
          if dx > best["dx"]:
            best = {
              "dx": dx,
              "steps": st,
              "term": term,
              "period": period,
              "reach": reach,
              "ka": ka,
              "ak": ak,
              "hk": hk,
            }
            print("NEW", best)

print("FINAL", best)
