# type: ignore
"""MuJoCo passive viewer 用：IMU 転倒下限の参考平面オーバーレイ（user_scn）。

物理モデル（MJCF）には geom を追加せず、viewer.user_scn に薄板 BOX を描画する。
config.VIEWER_TARGET_HEIGHT_PLANES で z [m] と rgba（薄赤半透明）を指定する。
"""

from __future__ import annotations

import numpy as np
import mujoco

from lib.experiment_context import ExperimentContext, build_experiment_context
from conf.schema import build_app_config


_DEFAULT_CTX: ExperimentContext | None = None


def _resolve_ctx(ctx: ExperimentContext | None) -> ExperimentContext:
  global _DEFAULT_CTX
  if ctx is not None:
    return ctx
  if _DEFAULT_CTX is None:
    # 既存呼び出し互換: ctx 未指定でも既定設定で overlay を描けるようにする。
    _DEFAULT_CTX = build_experiment_context(build_app_config())
  return _DEFAULT_CTX


def _plane_specs(ctx: ExperimentContext):
  """``termination.min_imu_z_stance`` を薄赤参考平面の z に使う。"""
  z = float(ctx.cfg.termination.min_imu_z_stance)
  rgba = (1.0, 0.25, 0.25, 0.28)
  return ((z, rgba),)


def apply_target_height_plane_overlay(viewer, ctx: ExperimentContext | None = None) -> None:
  """viewer.user_scn に目標高さの薄板 geom を設定する（sync 直前に呼ぶ）。"""
  resolved = _resolve_ctx(ctx)
  hx, hy = resolved.cfg.sim.viewer_height_plane_half_xy
  thickness = resolved.cfg.sim.viewer_height_plane_thickness
  identity = np.eye(3).flatten()

  viewer.user_scn.ngeom = 0
  for i, (z, rgba) in enumerate(_plane_specs(resolved)):
    mujoco.mjv_initGeom(
      viewer.user_scn.geoms[i],
      type=mujoco.mjtGeom.mjGEOM_BOX,
      size=[hx, hy, thickness],
      pos=[0.0, 0.0, float(z)],
      mat=identity,
      rgba=list(rgba),
    )
  viewer.user_scn.ngeom = len(_plane_specs(resolved))


def sync_viewer_with_height_overlay(viewer, ctx: ExperimentContext | None = None) -> None:
  """目標高さオーバーレイを載せて passive viewer を sync する。"""
  with viewer.lock():
    apply_target_height_plane_overlay(viewer, ctx)
  viewer.sync()
