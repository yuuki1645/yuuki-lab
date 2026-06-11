"""medium + 正しい upright バランス層の評価。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _paths import install  # noqa: E402

install()

import numpy as np  # noqa: E402

from runtime.config import load_run_config  # noqa: E402
from runtime.exp030_env import create_env, reset_env  # noqa: E402
from scripts.tune_forward import make_action_fn  # noqa: E402

PARAMS = dict(
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
  reach_hp=-0.12,
  ka=0.18,
  sw_ank=0.08,
  tor_sw=0.04,
)

_OBS_TILT_X = 4
_OBS_UPRIGHT = 6
_OBS_GYRO_X = 1
_OBS_L_CONTACT = 8
_OBS_R_CONTACT = 9
_L_ANK, _R_ANK = 3, 8
_L_HIP_P, _R_HIP_P = 1, 6
_TORSO_P = 11


def balance(action: list[float], obs: np.ndarray, *, ak: float, tk: float, hk: float) -> None:
  tilt = float(obs[_OBS_TILT_X])
  upright = float(obs[_OBS_UPRIGHT])
  gyro = float(obs[_OBS_GYRO_X])
  lc = float(obs[_OBS_L_CONTACT]) > 0.5
  rc = float(obs[_OBS_R_CONTACT]) > 0.5

  # 前傾（tilt>0）→ 体幹を後傾、支持足首で COM を戻す
  ankle = float(np.clip(-ak * tilt - 0.06 * gyro, -0.16, 0.16))
  torso = float(np.clip(-tk * tilt + hk * (upright - 0.62), -0.12, 0.12))

  if lc and not rc:
    action[_L_ANK] = float(np.clip(action[_L_ANK] + ankle, -1.0, 1.0))
    action[_L_HIP_P] = float(np.clip(action[_L_HIP_P] - 0.3 * ankle, -1.0, 1.0))
  elif rc and not lc:
    action[_R_ANK] = float(np.clip(action[_R_ANK] + ankle, -1.0, 1.0))
    action[_R_HIP_P] = float(np.clip(action[_R_HIP_P] - 0.3 * ankle, -1.0, 1.0))
  action[_TORSO_P] = float(np.clip(action[_TORSO_P] + torso, -1.0, 1.0))


def run(ak: float, tk: float, hk: float, *, max_steps: int = 1500) -> dict:
  cfg = load_run_config()
  env = create_env(cfg)
  fn = make_action_fn(PARAMS)
  obs, _ = reset_env(env, seed=42)
  x0 = float(env.data.site("imu_site").xpos[0])
  term = None
  for step in range(max_steps):
    a = list(fn(step, obs))
    if ak > 0 or tk > 0 or hk > 0:
      balance(a, np.asarray(obs), ak=ak, tk=tk, hk=hk)
    obs, _, terminated, info = env.step(tuple(a), episode_step=step)
    if terminated:
      term = info.get("termination_reason")
      break
  return {
    "dx": float(env.data.site("imu_site").xpos[0]) - x0,
    "steps": step + 1,
    "term": term,
  }


if __name__ == "__main__":
  print("open", run(0, 0, 0))
  for ak, tk, hk in [
    (0.5, 0.4, 0.0),
    (0.7, 0.5, 0.0),
    (0.7, 0.5, 0.3),
    (1.0, 0.6, 0.4),
    (1.2, 0.8, 0.5),
  ]:
    print(f"ak={ak} tk={tk} hk={hk}", run(ak, tk, hk))
