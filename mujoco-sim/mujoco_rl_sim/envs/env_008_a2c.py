import mujoco
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options
from scipy.spatial.transform import Rotation as R

import math
import time


class Env008A2C:
  """PPO用 Env007 と同じ MuJoCo モデル・観測・報酬。

  行動は [-1, 1] の1次元連続値。観測は (leg_x, pitch, 直前行動)。
  """

  def __init__(self):
    self.model = mujoco.MjModel.from_xml_path("../../mujoco_sim_assets/xmls/006_leg_1joint_dqn/main.xml")
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)
    self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
    apply_passive_viewer_options(self.viewer)

    self._max_ctrl_rad = math.radians(45.0)
    self._prev_action = 0.0

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    self.viewer.sync()
    self._prev_action = 0.0
    return self._get_obs()

  def step(self, action, visualize=False):
    a = float(action)
    if a > 1.0:
      a = 1.0
    elif a < -1.0:
      a = -1.0
    self.data.ctrl[0] = a * self._max_ctrl_rad

    mujoco.mj_step(self.model, self.data)
    self.viewer.sync()

    if visualize:
      time.sleep(self.model.opt.timestep)

    self._prev_action = a
    obs_next = self._get_obs()
    x = obs_next[0]
    reward = -x

    return obs_next, reward

  def _get_obs(self):
    leg_xpos = self.data.site("leg_site").xpos[0]
    leg_xquat = self.data.sensor("leg_quat").data.copy()

    rot = R.from_quat([leg_xquat[1], leg_xquat[2], leg_xquat[3], leg_xquat[0]])
    roll, pitch, yaw = rot.as_euler("xyz", degrees=True)

    return float(leg_xpos), float(pitch), float(self._prev_action)
