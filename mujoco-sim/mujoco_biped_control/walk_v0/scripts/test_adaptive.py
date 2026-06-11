"""適応的 reach スケールの評価。"""
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
term = None
for s in range(1500):
  a, _ = c.compute_action(step=s, obs=np.asarray(obs), env=env, control_dt=dt)
  o = np.asarray(obs)
  upright = float(o[6])
  a = list(a)
  # 直立が危険域: 遊脚 hip を中立側へ寄せて歩幅を縮小 + 体幹を起こす
  if upright < 0.56:
    scale = float(np.clip((upright - 0.48) / 0.08, 0.55, 1.0))
    for hip in (1, 6):
      neutral = p.base_hip_pitch
      a[hip] = float(np.clip(neutral + (a[hip] - neutral) * scale, -1, 1))
    a[11] = float(np.clip(a[11] + 0.25 * (0.56 - upright), -1, 1))
  obs, _, terminated, info = env.step(tuple(a), episode_step=s)
  if terminated:
    term = info.get("termination_reason")
    break
dx = float(env.data.site("imu_site").xpos[0]) - x0
print("dx", dx, "steps", s + 1, "term", term)
