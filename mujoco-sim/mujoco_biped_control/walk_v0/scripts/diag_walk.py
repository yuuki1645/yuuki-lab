"""WalkController の dx 時系列。"""
import sys
sys.path.insert(0, ".")
from _paths import install
install()
import numpy as np
from controller.walk import WalkController
from runtime.config import ControlParams, load_run_config
from runtime.exp030_env import create_env, reset_env

cfg = load_run_config()
env = create_env(cfg)
dt = float(env._ctx.cfg.sim.control_timestep_s)
p = ControlParams(
  balance_ankle_gain=1.0,
  balance_torso_tilt_gain=0.6,
  balance_upright_gain=0.4,
  balance_height_gain=0.0,
  forward_dx_gain=0.0,
  upright_swing_floor=1.0,
  upright_swing_min=0.0,
)
c = WalkController(p)
obs, _ = reset_env(env, seed=42)
x0 = float(env.data.site("imu_site").xpos[0])
for s in range(1500):
  a, _ = c.compute_action(step=s, obs=np.asarray(obs), env=env, control_dt=dt)
  obs, _, term, info = env.step(a, episode_step=s)
  if s % 100 == 0 or term:
    x = float(env.data.site("imu_site").xpos[0]) - x0
    print(f"s={s} x={x:+.3f} upright={info.get('upright'):.3f} term={info.get('termination_reason')}")
  if term:
    break
