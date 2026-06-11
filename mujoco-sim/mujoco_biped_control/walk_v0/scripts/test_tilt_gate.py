"""傾きゲート付きバランスの評価。"""
import sys
sys.path.insert(0, ".")
from _paths import install
install()
import numpy as np
from scripts.tune_forward import make_action_fn, eval_params
from runtime.config import load_run_config
from runtime.exp030_env import create_env, reset_env

PARAMS = dict(
  hp=-0.34, kn=0.05, ank=-0.12, tor=0.14, ds=0.06, period=1.2,
  roll=0.07, rs=0.7, shp=-0.03, skn=-0.02, sank=-0.08,
  push_hp=0.06, push_kn=-0.04, push_ank=-0.15, lift_hp=0.05,
  reach_hp=-0.12, ka=0.18, sw_ank=0.08, tor_sw=0.04,
)

def run(*, tilt_start: float, ak: float, tk: float, hk: float, max_steps=1500):
  cfg = load_run_config()
  env = create_env(cfg)
  fn = make_action_fn(PARAMS)
  obs, _ = reset_env(env, seed=42)
  x0 = float(env.data.site("imu_site").xpos[0])
  term = None
  for step in range(max_steps):
    a = list(fn(step, obs))
    o = np.asarray(obs)
    tilt = float(o[4])
    upright = float(o[6])
    gyro = float(o[1])
    lc, rc = float(o[8]) > 0.5, float(o[9]) > 0.5
    excess = max(0.0, tilt - tilt_start)
    ankle = float(np.clip(-ak * excess - 0.05 * gyro, -0.14, 0.14))
    torso = float(np.clip(-tk * excess + hk * (upright - 0.62), -0.10, 0.10))
    if lc and not rc:
      a[3] = np.clip(a[3] + ankle, -1, 1)
      a[1] = np.clip(a[1] - 0.25 * ankle, -1, 1)
    elif rc and not lc:
      a[8] = np.clip(a[8] + ankle, -1, 1)
      a[6] = np.clip(a[6] - 0.25 * ankle, -1, 1)
    a[11] = np.clip(a[11] + torso, -1, 1)
    obs, _, terminated, info = env.step(tuple(a), episode_step=step)
    if terminated:
      term = info.get("termination_reason")
      break
  return float(env.data.site("imu_site").xpos[0]) - x0, step + 1, term

print("open", eval_params(PARAMS, max_steps=1500, seed=42))
for ts in [0.50, 0.55, 0.60, 0.65, 0.70]:
  for ak in [0.8, 1.2, 1.6]:
    dx, st, term = run(tilt_start=ts, ak=ak, tk=0.5, hk=0.3)
    if dx > 0.5 or st >= 200:
      print(f"ts={ts} ak={ak} dx={dx:+.3f} steps={st} term={term}")
