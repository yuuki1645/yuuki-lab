"""1.47m 構成の dx 時系列。"""
import sys
sys.path.insert(0, ".")
from _paths import install
install()
from dataclasses import replace
import numpy as np
from controller.walk import WalkController
from runtime.config import load_control_params, load_run_config
from runtime.exp030_env import create_env, reset_env

p = replace(
  load_control_params(),
  balance_ankle_gain=1.0,
  balance_torso_tilt_gain=0.6,
  balance_upright_gain=0.4,
  balance_tilt_deadband=0.0,
  balance_upright_activate=0.0,
  foot_place_gain=0,
  balance_height_gain=0.18,
  cycle_period_s=1.0,
  swing_reach_hip=-0.10,
)
cfg = load_run_config()
env = create_env(cfg)
dt = float(env._ctx.cfg.sim.control_timestep_s)
c = WalkController(p)
obs, _ = reset_env(env, seed=42)
x0 = float(env.data.site("imu_site").xpos[0])
for s in range(900):
  a, _ = c.compute_action(step=s, obs=np.asarray(obs), env=env, control_dt=dt)
  obs, _, term, info = env.step(a, episode_step=s)
  if s % 50 == 0 or term:
    x = float(env.data.site("imu_site").xpos[0]) - x0
    print(f"s={s} x={x:+.3f} upright={info.get('upright'):.3f} term={info.get('termination_reason')}")
  if term:
    break
