import sys
sys.path.insert(0, ".")
from _paths import install
install()
from dataclasses import replace
from controller.walk import WalkController
from runtime.config import load_control_params, load_run_config
from runtime.exp030_env import create_env, reset_env
import numpy as np

for st, tg in [(0.56, 0.30), (0.57, 0.35), (0.58, 0.40), (0.59, 0.45)]:
  p = replace(load_control_params(), survival_upright_thresh=st, survival_torso_gain=tg)
  cfg = load_run_config()
  env = create_env(cfg)
  dt = float(env._ctx.cfg.sim.control_timestep_s)
  c = WalkController(p)
  obs, _ = reset_env(env, seed=42)
  x0 = float(env.data.site("imu_site").xpos[0])
  for s in range(1500):
    a, _ = c.compute_action(step=s, obs=np.asarray(obs), env=env, control_dt=dt)
    obs, _, term, info = env.step(a, episode_step=s)
    if term:
      dx = float(env.data.site("imu_site").xpos[0]) - x0
      print(f"st={st} tg={tg} dx={dx:+.3f} steps={s+1} {info.get('termination_reason')}")
      break
