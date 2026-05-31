"""ボディフレーム姿勢量（ヨーに依存しない前後傾き・水平傾き・正面ずれ）。"""

from __future__ import annotations

import mujoco
import numpy as np

BODY_NAME = "basket_thigh"
WORLD_FORWARD_X = 1.0
WORLD_FORWARD_Y = 0.0
WORLD_FORWARD_Z = 0.0


def body_xaxis_world(data: mujoco.MjData, body_name: str = BODY_NAME) -> np.ndarray:
  """ルートボディのローカル +X 軸のワールド単位ベクトル。"""
  xmat = data.body(body_name).xmat.reshape(3, 3)
  return xmat[:, 0].copy()


def pose_metrics(
  imu_zaxis: np.ndarray,
  data: mujoco.MjData,
  *,
  body_name: str = BODY_NAME,
) -> tuple[float, float, float]:
  """(lean_fwd_body, heading_align, tilt_horiz) を返す。

  lean_fwd_body: imu 上向き軸がボディ +X 方向へ傾く成分（前傾で正）
  heading_align: dot(body +X, world +X)。1 に近いほどタスク正面を向く
  tilt_horiz: sqrt(zaxis_x^2 + zaxis_y^2)。ヨーに依存しない水平面傾き
  """
  body_x = body_xaxis_world(data, body_name)
  lean_fwd_body = float(np.dot(imu_zaxis, body_x))
  heading_align = float(
    body_x[0] * WORLD_FORWARD_X
    + body_x[1] * WORLD_FORWARD_Y
    + body_x[2] * WORLD_FORWARD_Z
  )
  tilt_horiz = float(np.hypot(float(imu_zaxis[0]), float(imu_zaxis[1])))
  return lean_fwd_body, heading_align, tilt_horiz
