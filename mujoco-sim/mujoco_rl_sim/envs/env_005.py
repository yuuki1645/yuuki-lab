# type: ignore

import math
import mujoco
import mujoco.viewer
import numpy as np
import time
from scipy.spatial.transform import Rotation as R

from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

class Env005:
  def __init__(self):
    self.model = mujoco.MjModel.from_xml_path("../../mujoco_sim_assets/xmls/005_leg_1joint/main.xml")
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)
    self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
    apply_passive_viewer_options(self.viewer)

    self._leg_body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "leg")

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    self.viewer.sync()
    obs = self._get_obs()
    return obs

  def step(self, action, visualize=False):
    self.data.ctrl[0] = math.radians(-10.0 if action == 0 else 10.0)

    mujoco.mj_step(self.model, self.data)

    self.viewer.sync()
    if visualize:
      time.sleep(self.model.opt.timestep)

    obs_next = self._get_obs()

    # root ジョイントのX座標
    # x = self.data.joint("root").qpos[0]
    x = obs_next[0]

    reward = x

    return obs_next, reward

  # def _sensor_vec(self, name: str, dim: int):
  #   sid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, name)
  #   adr = int(self.model.sensor_adr[sid])
  #   vec = np.asarray(self.data.sensordata[adr : adr + dim], dtype=np.float32).copy()

  #   print(f"vec: {vec}")
  #   return vec

  # def _leg_body_world_y_tilt_deg(self) -> float:
  #   """body `leg` のワールド座標系 Y 周りの傾き（度）。内蔵 Z-Y-X の中央角（Ry / pitch）。"""
  #   R = self.data.xmat[self._leg_body_id].reshape(3, 3)
  #   cos_pitch = math.hypot(float(R[0, 0]), float(R[1, 0]))
  #   return math.degrees(math.atan2(-float(R[2, 0]), cos_pitch))

  def _get_obs(self):
    leg_xpos = self.data.site("leg_site").xpos[0]
    leg_xquat = self.data.sensor("leg_quat").data.copy()

    rot = R.from_quat([leg_xquat[1], leg_xquat[2], leg_xquat[3], leg_xquat[0]])
    roll, pitch, yaw = rot.as_euler("xyz", degrees=True)

    # print(f"leg_xpos: x: {leg_xpos[0]: 8.2f}, y: {leg_xpos[1]: 8.2f}, z: {leg_xpos[2]: 8.2f}")
    # print(f"roll: {roll: 8.0f}, pitch: {pitch: 8.0f}, yaw: {yaw: 8.0f}")

    return float(leg_xpos), float(pitch)
