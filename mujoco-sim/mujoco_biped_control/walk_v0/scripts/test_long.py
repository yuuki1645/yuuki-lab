"""長距離前進の組合せテスト。"""
import sys
sys.path.insert(0, ".")
from _paths import install
install()
import numpy as np
from controller.walk import WalkController
from runtime.config import ControlParams, load_run_config
from runtime.exp030_env import create_env, reset_env

def eval_cfg(p: ControlParams) -> dict:
  cfg = load_run_config()
  env = create_env(cfg)
  dt = float(env._ctx.cfg.sim.control_timestep_s)
  c = WalkController(p)
  obs, _ = reset_env(env, seed=42)
  x0 = float(env.data.site("imu_site").xpos[0])
  term = None
  for s in range(1500):
    a, _ = c.compute_action(step=s, obs=np.asarray(obs), env=env, control_dt=dt)
    obs, _, terminated, info = env.step(a, episode_step=s)
    if terminated:
      term = info.get("termination_reason")
      break
  return {
    "dx": float(env.data.site("imu_site").xpos[0]) - x0,
    "steps": s + 1,
    "term": term,
  }

cases = {
  "A_base": ControlParams(),
  "B_no_scale": ControlParams(upright_swing_floor=1.0, upright_swing_min=0.0, balance_height_gain=0.0, forward_dx_gain=0.0),
  "C_reach": ControlParams(upright_swing_floor=1.0, upright_swing_min=0.0, balance_height_gain=0.0, forward_dx_gain=0.0, swing_reach_hip=-0.14, push_off_ankle=-0.17),
  "D_gate": ControlParams(
    upright_swing_floor=1.0, upright_swing_min=0.0, balance_height_gain=0.0, forward_dx_gain=0.0,
    swing_reach_hip=-0.14, push_off_ankle=-0.17,
    balance_tilt_deadband=0.72, balance_ankle_gain=1.4, balance_upright_activate=0.56,
  ),
  "E_place": ControlParams(
    upright_swing_floor=1.0, upright_swing_min=0.0, balance_height_gain=0.0, forward_dx_gain=0.0,
    swing_reach_hip=-0.14, push_off_ankle=-0.17,
    balance_tilt_deadband=0.72, balance_ankle_gain=1.4, balance_upright_activate=0.56,
    step_length_target=0.16, foot_place_gain=0.45,
  ),
}

for name, p in cases.items():
  print(name, eval_cfg(p))
