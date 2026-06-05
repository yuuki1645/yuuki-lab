# type: ignore
"""MuJoCo passive viewer 用：目標 IMU 高さの半透明平面オーバーレイ（user_scn）。

物理モデル（MJCF）には geom を追加せず、viewer.user_scn に薄板 BOX を描画する。
config.VIEWER_TARGET_HEIGHT_PLANES で z [m] と rgba を指定する。
"""

from __future__ import annotations

import numpy as np
import mujoco


def _plane_specs():
  """config から (z, rgba) の列を取得する。"""
  import config

  return config.VIEWER_TARGET_HEIGHT_PLANES


def apply_target_height_plane_overlay(viewer) -> None:
  """viewer.user_scn に目標高さの薄板 geom を設定する（sync 直前に呼ぶ）。"""
  import config

  hx, hy = config.VIEWER_HEIGHT_PLANE_HALF_XY
  thickness = config.VIEWER_HEIGHT_PLANE_THICKNESS
  identity = np.eye(3).flatten()

  viewer.user_scn.ngeom = 0
  for i, (z, rgba) in enumerate(_plane_specs()):
    mujoco.mjv_initGeom(
      viewer.user_scn.geoms[i],
      type=mujoco.mjtGeom.mjGEOM_BOX,
      size=[hx, hy, thickness],
      pos=[0.0, 0.0, float(z)],
      mat=identity,
      rgba=list(rgba),
    )
  viewer.user_scn.ngeom = len(_plane_specs())


def sync_viewer_with_height_overlay(viewer) -> None:
  """目標高さオーバーレイを載せて passive viewer を sync する。"""
  with viewer.lock():
    apply_target_height_plane_overlay(viewer)
  viewer.sync()
