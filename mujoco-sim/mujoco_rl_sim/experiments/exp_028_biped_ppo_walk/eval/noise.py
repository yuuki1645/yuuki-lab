"""Eval 用初期姿勢ノイズ（stand keyframe 適用後に加算）。

学習 ``env.reset()`` には影響しない。``reset_eval`` からのみ呼ぶ。
"""

from __future__ import annotations

import mujoco
import numpy as np

from eval.spec import (
  APPLY_ROOT_XY_POSITION_NOISE,
  JOINT_NOISE_RAD,
  ROOT_ANG_VEL_NOISE_RAD_S,
  ROOT_LIN_VEL_NOISE_M_S,
  ROOT_YAW_NOISE_RAD,
)
from lib.actuators import JOINT_NAMES

_ROOT_JOINT_NAME = "root"


def _quat_mul(q: np.ndarray, r: np.ndarray) -> np.ndarray:
  """Hamilton 積（MuJoCo 慣習 w,x,y,z）。"""
  w1, x1, y1, z1 = q
  w2, x2, y2, z2 = r
  return np.array(
    [
      w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
      w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
      w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
      w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ],
    dtype=np.float64,
  )


def _quat_normalize(q: np.ndarray) -> np.ndarray:
  norm = float(np.linalg.norm(q))
  if norm < 1e-12:
    return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
  return q / norm


def _quat_from_yaw(yaw_rad: float) -> np.ndarray:
  """世界 Z 軸まわりの回転（w,x,y,z）。"""
  half = 0.5 * float(yaw_rad)
  return np.array([np.cos(half), 0.0, 0.0, np.sin(half)], dtype=np.float64)


def apply_initial_pose_noise(
  model: mujoco.MjModel,
  data: mujoco.MjData,
  rng: np.random.Generator,
) -> dict[str, float | list[float]]:
  """stand 適用済み state に初期ノイズを加える。適用値のサマリを返す。"""
  root_jnt_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, _ROOT_JOINT_NAME)
  if root_jnt_id < 0:
    raise ValueError(f"joint not found: {_ROOT_JOINT_NAME!r}")

  root_qpos_adr = int(model.jnt_qposadr[root_jnt_id])
  root_qvel_adr = int(model.jnt_dofadr[root_jnt_id])

  applied: dict[str, float | list[float]] = {}

  # --- ルートヨー（クォータニオン左乗算）---
  yaw = float(rng.uniform(-ROOT_YAW_NOISE_RAD, ROOT_YAW_NOISE_RAD))
  quat = data.qpos[root_qpos_adr + 3 : root_qpos_adr + 7].copy()
  quat_new = _quat_normalize(_quat_mul(_quat_from_yaw(yaw), quat))
  data.qpos[root_qpos_adr + 3 : root_qpos_adr + 7] = quat_new
  applied["root_yaw_noise_deg"] = float(np.degrees(yaw))

  # --- ルート X/Y 位置（v0 では無効）---
  if APPLY_ROOT_XY_POSITION_NOISE:
    dx = float(rng.uniform(-0.02, 0.02))
    dy = float(rng.uniform(-0.02, 0.02))
    data.qpos[root_qpos_adr] += dx
    data.qpos[root_qpos_adr + 1] += dy
    applied["root_xy_noise_m"] = [dx, dy]

  # --- 関節角（12 DOF）---
  joint_noise_deg: list[float] = []
  for joint_name in JOINT_NAMES:
    jnt_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    qpos_adr = int(model.jnt_qposadr[jnt_id])
    delta = float(rng.uniform(-JOINT_NOISE_RAD, JOINT_NOISE_RAD))
    lo, hi = model.jnt_range[jnt_id]
    data.qpos[qpos_adr] = float(np.clip(data.qpos[qpos_adr] + delta, lo, hi))
    joint_noise_deg.append(float(np.degrees(delta)))
  applied["joint_noise_deg"] = joint_noise_deg

  # --- ルート初速度（freejoint 6 DOF）---
  lin_noise = rng.uniform(-ROOT_LIN_VEL_NOISE_M_S, ROOT_LIN_VEL_NOISE_M_S, size=3)
  ang_noise = rng.uniform(-ROOT_ANG_VEL_NOISE_RAD_S, ROOT_ANG_VEL_NOISE_RAD_S, size=3)
  data.qvel[root_qvel_adr : root_qvel_adr + 3] += lin_noise
  data.qvel[root_qvel_adr + 3 : root_qvel_adr + 6] += ang_noise
  applied["root_lin_vel_noise_m_s"] = [float(v) for v in lin_noise]
  applied["root_ang_vel_noise_rad_s"] = [float(v) for v in ang_noise]

  mujoco.mj_forward(model, data)
  return applied
