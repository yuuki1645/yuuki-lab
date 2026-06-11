"""開ループ歩容 + バランス層の簡易評価（開発用）。"""

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

# tune_forward refine 付近のベスト候補
BASE = dict(
  hp=-0.34,
  kn=0.05,
  ank=-0.12,
  tor=0.14,
  ds=0.06,
  period=1.1,
  roll=0.07,
  rs=0.7,
  shp=-0.03,
  skn=-0.02,
  sank=-0.08,
  push_hp=0.06,
  push_kn=-0.04,
  push_ank=-0.18,
  lift_hp=0.05,
  reach_hp=-0.14,
  ka=0.24,
  sw_ank=0.08,
  tor_sw=0.04,
)

_OBS_TILT_X = 4
_OBS_UPRIGHT = 7
_OBS_L_CONTACT = 8
_OBS_R_CONTACT = 9
_OBS_SSP = 14

_L_ANK = 3
_R_ANK = 8
_L_HIP_P = 1
_R_HIP_P = 6
_TORSO_P = 11


def apply_balance(
  action: list[float],
  obs: np.ndarray,
  *,
  ankle_k: float,
  hip_k: float,
  torso_k: float,
) -> None:
  """支持脚のみ IMU サーボで姿勢回復（遊脚は触らない）。"""
  tilt_x = float(obs[_OBS_TILT_X])
  upright = float(obs[_OBS_UPRIGHT])
  l_on = float(obs[_OBS_L_CONTACT]) > 0.5
  r_on = float(obs[_OBS_R_CONTACT]) > 0.5

  pitch_err = float(np.clip(1.0 - upright, -0.05, 0.25))
  ankle_corr = float(np.clip(-ankle_k * tilt_x, -0.12, 0.12))
  hip_corr = float(np.clip(-hip_k * tilt_x, -0.08, 0.08))
  torso_corr = float(np.clip(torso_k * pitch_err, -0.06, 0.12))

  if l_on and not r_on:
    action[_L_ANK] = float(np.clip(action[_L_ANK] + ankle_corr, -1.0, 1.0))
    action[_L_HIP_P] = float(np.clip(action[_L_HIP_P] + hip_corr, -1.0, 1.0))
  elif r_on and not l_on:
    action[_R_ANK] = float(np.clip(action[_R_ANK] + ankle_corr, -1.0, 1.0))
    action[_R_HIP_P] = float(np.clip(action[_R_HIP_P] + hip_corr, -1.0, 1.0))
  action[_TORSO_P] = float(np.clip(action[_TORSO_P] + torso_corr, -1.0, 1.0))


def run(
  *,
  ankle_k: float,
  hip_k: float,
  torso_k: float,
  max_steps: int = 1500,
  seed: int = 42,
) -> dict:
  cfg = load_run_config()
  env = create_env(cfg)
  fn = make_action_fn(BASE)
  obs, _ = reset_env(env, seed=seed)
  x0 = float(env.data.site("imu_site").xpos[0])
  term = None
  for step in range(max_steps):
    a = list(fn(step, obs))
    apply_balance(a, np.asarray(obs), ankle_k=ankle_k, hip_k=hip_k, torso_k=torso_k)
    obs, _, terminated, info = env.step(tuple(a), episode_step=step)
    if terminated:
      term = info.get("termination_reason")
      break
  dx = float(env.data.site("imu_site").xpos[0]) - x0
  return {"dx": dx, "steps": step + 1, "term": term}


def main() -> None:
  print("open loop only:", run(ankle_k=0, hip_k=0, torso_k=0))
  combos = [
    (0.4, 0.15, 0.04),
    (0.6, 0.20, 0.06),
    (0.8, 0.25, 0.08),
    (1.0, 0.30, 0.10),
    (1.2, 0.35, 0.12),
  ]
  best = None
  for ak, hk, tk in combos:
    out = run(ankle_k=ak, hip_k=hk, torso_k=tk)
    print(f"ankle={ak} hip={hk} torso={tk} -> {out}")
    if best is None or out["dx"] > best["dx"]:
      best = {**out, "ankle_k": ak, "hip_k": hk, "torso_k": tk}
  print("BEST", best)


if __name__ == "__main__":
  main()
