import mujoco
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options
from scipy.spatial.transform import Rotation as R

import math
import time


class Env006DQN:
  def __init__(self):
    self.model = mujoco.MjModel.from_xml_path("../../mujoco_sim_assets/xmls/006_leg_1joint_dqn/main.xml")
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)
    self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
    apply_passive_viewer_options(self.viewer)

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    self.viewer.sync()
    obs = self._get_obs()

    return obs

  def step(self, action, visualize=False):
    self.data.ctrl[0] = math.radians(action)

    mujoco.mj_step(self.model, self.data)
    self.viewer.sync()

    if visualize:
      time.sleep(self.model.opt.timestep)

    obs_next = self._get_obs()
    x = obs_next[0]
    reward = X

    return obs_next, reward

  def _get_obs(self):
    leg_xpos = self.data.site("leg_site").xpos[0]
    leg_xquat = self.data.sensor("leg_quat").data.copy()

    rot = R.from_quat([leg_xquat[1], leg_xquat[2], leg_xquat[3], leg_xquat[0]])
    roll, pitch, yaw = rot.as_euler("xyz", degrees=True)

    return float(leg_xpos), float(pitch)