"""インシデント瞬間の MuJoCo 状態・画像スナップショット。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mujoco
import numpy as np


def save_physics_snapshot(
  run_dir: Path,
  *,
  step: int,
  model: mujoco.MjModel,
  data: mujoco.MjData,
) -> Path:
  """qpos / qvel / time を npz で保存（seed 再現 + step シークより確実）。"""
  out_dir = run_dir / "incidents" / f"step_{step:05d}"
  out_dir.mkdir(parents=True, exist_ok=True)
  path = out_dir / "state.npz"
  np.savez(
    path,
    qpos=np.array(data.qpos, copy=True),
    qvel=np.array(data.qvel, copy=True),
    time=np.array([data.time]),
    ctrl=np.array(data.ctrl, copy=True),
  )
  return out_dir


def render_frame_png(
  model: mujoco.MjModel,
  data: mujoco.MjData,
  out_path: Path,
  *,
  width: int = 1280,
  height: int = 720,
) -> Path:
  """オフスクリーンで 1 フレームを PNG 保存（可視理解用）。"""
  renderer = mujoco.Renderer(model, width=width, height=height)
  try:
    renderer.update_scene(data)
    img = renderer.render()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
      import imageio.v3 as iio

      iio.imwrite(out_path, img)
    except ImportError:
      np.save(out_path.with_suffix(".npy"), img)
  finally:
    renderer.close()
  return out_path


def load_physics_snapshot(snapshot_dir: Path) -> dict[str, np.ndarray]:
  path = snapshot_dir / "state.npz"
  with np.load(path) as z:
    return {k: z[k] for k in z.files}


def apply_snapshot(model: mujoco.MjModel, data: mujoco.MjData, snap: dict[str, np.ndarray]) -> None:
  data.qpos[:] = snap["qpos"]
  data.qvel[:] = snap["qvel"]
  if "ctrl" in snap:
    data.ctrl[:] = snap["ctrl"]
  data.time = float(snap["time"][0])
  mujoco.mj_forward(model, data)
