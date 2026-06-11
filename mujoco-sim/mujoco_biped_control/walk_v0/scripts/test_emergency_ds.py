"""upright 急落時に DS 姿勢を保持して回復。"""
import sys
sys.path.insert(0, ".")
from _paths import install
install()
from dataclasses import replace
import numpy as np
from controller.walk import WalkController
from runtime.config import load_control_params, load_run_config
from runtime.exp030_env import create_env, reset_env

p = load_control_params()
cfg = load_run_config()
env = create_env(cfg)
dt = float(env._ctx.cfg.sim.control_timestep_s)
c = WalkController(p)
obs, _ = reset_env(env, seed=42)
x0 = float(env.data.site("imu_site").xpos[0])
hold = 0
for s in range(1500):
  o = np.asarray(obs)
  u = float(o[6])
  if u < 0.52:
    hold = max(hold, 8)
  if hold > 0:
    hold -= 1
    hp, kn, ank, tor = p.base_hip_pitch, p.base_knee, p.base_ankle_pitch, p.base_torso_pitch
    a = (0.0, hp, kn, ank, 0.0, 0.0, hp, kn, ank, 0.0, 0.0, tor + 0.08)
  else:
    a, _ = c.compute_action(step=s, obs=o, env=env, control_dt=dt)
  obs, _, term, info = env.step(a, episode_step=s)
  if term:
    print(float(env.data.site("imu_site").xpos[0]) - x0, s + 1, info.get("termination_reason"))
    break
else:
  print(float(env.data.site("imu_site").xpos[0]) - x0, 1500, None)
