"""接触同期 FSM + 開ループ歩容の評価。"""

from __future__ import annotations

import enum
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _paths import install  # noqa: E402

install()

import numpy as np  # noqa: E402

from runtime.config import load_run_config  # noqa: E402
from runtime.exp030_env import create_env, reset_env  # noqa: E402

# obs indices
_OBS_DX = 0
_OBS_GYRO_X = 1
_OBS_TILT_X = 4
_OBS_UPRIGHT = 7
_OBS_L_CONTACT = 8
_OBS_R_CONTACT = 9
_OBS_SSP = 14

_L_HIP_R, _L_HIP_P, _L_KNEE, _L_ANK = 0, 1, 2, 3
_R_HIP_R, _R_HIP_P, _R_KNEE, _R_ANK = 5, 6, 7, 8
_TORSO_P = 11


class Phase(enum.Enum):
  DS = "ds"
  SWING_R = "swing_r"
  SWING_L = "swing_l"


@dataclass
class GaitParams:
  hp: float = -0.34
  kn: float = 0.05
  ank: float = -0.12
  tor: float = 0.14
  roll: float = 0.07
  rs: float = 0.7
  shp: float = -0.03
  skn: float = -0.02
  sank: float = -0.08
  push_hp: float = 0.06
  push_kn: float = -0.04
  push_ank: float = -0.16
  lift_hp: float = 0.05
  reach_hp: float = -0.14
  ka: float = 0.22
  sw_ank: float = 0.08
  tor_sw: float = 0.04
  swing_steps: int = 28
  ds_steps: int = 4
  # バランス
  ankle_k: float = 0.55
  torso_k: float = 0.10
  gyro_d: float = 0.08


def _lerp(a: float, b: float, t: float) -> float:
  t = float(np.clip(t, 0.0, 1.0))
  return a + (b - a) * t


def _tri(t: float) -> float:
  t = float(np.clip(t, 0.0, 1.0))
  return 1.0 - abs(2.0 * t - 1.0)


def _swing_hip(p: GaitParams, t: float) -> float:
  if t < 0.25:
    return p.hp + p.lift_hp * (t / 0.25)
  if t < 0.65:
    return p.hp + p.reach_hp
  w = (t - 0.65) / 0.35
  return _lerp(p.hp + p.reach_hp, p.hp, w)


class ContactGait:
  def __init__(self, params: GaitParams):
    self.p = params
    self.phase = Phase.DS
    self.phase_step = 0
    self.step_count = 0
    self._prev_action = [0.0] * 12
    self._last_swing = ""

  def _contacts(self, obs: np.ndarray) -> tuple[bool, bool]:
    return float(obs[_OBS_L_CONTACT]) > 0.5, float(obs[_OBS_R_CONTACT]) > 0.5

  def _advance_phase(self, obs: np.ndarray) -> None:
    lc, rc = self._contacts(obs)
    p = self.p
    if self.phase == Phase.DS:
      if self.phase_step >= p.ds_steps - 1:
        if lc and not rc:
          self.phase = Phase.SWING_R
          self.phase_step = 0
        elif rc and not lc:
          self.phase = Phase.SWING_L
          self.phase_step = 0
    elif self.phase == Phase.SWING_R:
      if rc and self.phase_step > 4:
        self.phase = Phase.DS
        self.phase_step = 0
        self.step_count += 1
        self._last_swing = "right"
      elif self.phase_step >= p.swing_steps:
        self.phase = Phase.DS
        self.phase_step = 0
    elif self.phase == Phase.SWING_L:
      if lc and self.phase_step > 4:
        self.phase = Phase.DS
        self.phase_step = 0
        self.step_count += 1
        self._last_swing = "left"
      elif self.phase_step >= p.swing_steps:
        self.phase = Phase.DS
        self.phase_step = 0

  def _open_loop(self, t: float, *, swing_right: bool) -> list[float]:
    p = self.p
    push = max(0.0, 1.0 - t / 0.25)
    tri = _tri(t)
    swing_kn = p.kn + p.ka * tri
    swing_ank = p.sw_ank if t < 0.5 else p.ank
    tor = p.tor + p.tor_sw
    swing_hp = _swing_hip(p, t)

    if swing_right:
      return [
        p.roll,
        p.hp + p.shp - p.push_hp * push,
        p.kn + p.skn - p.push_kn * push,
        p.ank + p.sank - p.push_ank * push,
        0.0,
        p.roll * p.rs,
        swing_hp,
        swing_kn,
        swing_ank,
        0.0,
        0.0,
        tor,
      ]
    return [
      -p.roll * p.rs,
      swing_hp,
      swing_kn,
      swing_ank,
      0.0,
      -p.roll,
      p.hp + p.shp - p.push_hp * push,
      p.kn + p.skn - p.push_kn * push,
      p.ank + p.sank - p.push_ank * push,
      0.0,
      0.0,
      tor,
    ]

  def _balance(self, action: list[float], obs: np.ndarray) -> None:
    p = self.p
    tilt = float(obs[_OBS_TILT_X])
    upright = float(obs[_OBS_UPRIGHT])
    gyro_x = float(obs[_OBS_GYRO_X])
    lc, rc = self._contacts(obs)

    ankle = float(np.clip(-p.ankle_k * tilt - p.gyro_d * gyro_x, -0.14, 0.14))
    torso = float(np.clip(p.torso_k * (1.0 - upright), -0.05, 0.15))

    if lc and not rc:
      action[_L_ANK] = float(np.clip(action[_L_ANK] + ankle, -1.0, 1.0))
    elif rc and not lc:
      action[_R_ANK] = float(np.clip(action[_R_ANK] + ankle, -1.0, 1.0))
    action[_TORSO_P] = float(np.clip(action[_TORSO_P] + torso, -1.0, 1.0))

  def compute(self, obs: np.ndarray) -> tuple[tuple[float, ...], dict]:
    p = self.p
    self._advance_phase(obs)

    if self.phase == Phase.DS:
      w = (self.phase_step + 1) / max(p.ds_steps, 1)
      action = self._prev_action[:]
      targets = (
        (_L_HIP_P, p.hp),
        (_L_KNEE, p.kn),
        (_L_ANK, p.ank),
        (_R_HIP_P, p.hp),
        (_R_KNEE, p.kn),
        (_R_ANK, p.ank),
        (_TORSO_P, p.tor),
      )
      for idx, val in targets:
        action[idx] = _lerp(action[idx], val, w)
    else:
      t = self.phase_step / max(p.swing_steps - 1, 1)
      action = self._open_loop(
        t, swing_right=(self.phase == Phase.SWING_R)
      )

    self._balance(action, obs)
    clipped = tuple(float(np.clip(a, -1.0, 1.0)) for a in action)
    self._prev_action = list(clipped)
    self.phase_step += 1
    dbg = {
      "phase": self.phase.value,
      "phase_step": float(self.phase_step),
      "step_count": float(self.step_count),
    }
    return clipped, dbg


def evaluate(params: GaitParams, *, max_steps: int = 1500, seed: int = 42) -> dict:
  cfg = load_run_config()
  env = create_env(cfg)
  gait = ContactGait(params)
  obs, _ = reset_env(env, seed=seed)
  x0 = float(env.data.site("imu_site").xpos[0])
  term = None
  for step in range(max_steps):
    action, _ = gait.compute(np.asarray(obs))
    obs, _, terminated, info = env.step(action, episode_step=step)
    if terminated:
      term = info.get("termination_reason")
      break
  dx = float(env.data.site("imu_site").xpos[0]) - x0
  return {"dx": dx, "steps": step + 1, "term": term, "steps_taken": gait.step_count}


def main() -> None:
  base = GaitParams()
  print("base", evaluate(base))
  for reach in [-0.12, -0.14, -0.16, -0.18]:
    for push in [-0.14, -0.16, -0.18, -0.20]:
      for ak in [0.3, 0.5, 0.7]:
        p = GaitParams(reach_hp=reach, push_ank=push, ankle_k=ak)
        out = evaluate(p)
        if out["dx"] > 0.2:
          print(
            "reach=%.2f push=%.2f ak=%.1f -> dx=%+.3f steps=%d term=%s gait_steps=%d"
            % (reach, push, ak, out["dx"], out["steps"], out["term"], out["steps_taken"])
          )
  best = evaluate(GaitParams(reach_hp=-0.16, push_ank=-0.18, ankle_k=0.5, swing_steps=26))
  print("candidate", best)


if __name__ == "__main__":
  main()
