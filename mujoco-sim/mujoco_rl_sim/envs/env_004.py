# type: ignore

import math
import mujoco
import mujoco.viewer
import numpy as np


class Env004:
  def __init__(self):
    self.model = mujoco.MjModel.from_xml_path("../../mujoco_sim_assets/xmls/005_leg_1joint/main.xml")
    self.data = mujoco.MjData(self.model)
    self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
    self.root_joint_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "root")
    # print(f"self.root_joint_id: {self.root_joint_id}")

  def reset(self):
    obs = self._get_obs()
    return obs

  def step(self, action):
    self.data.ctrl[0] = math.radians(-10.0 if action == 0 else 10.0)
    mujoco.mj_step(self.model, self.data)
    # print(f"time: {self.data.time:.2f}")
    # print(f"qpos.root: {self.data.joint("root").qpos}")
    self.viewer.sync()

    obs_next = self._get_obs()

    # root ジョイントのX座標
    x = self.data.qpos[self.model.jnt_qposadr[self.root_joint_id]]
    reward = x

    return obs_next, reward

  def _sensor_vec(self, name: str, dim: int):
    sid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, name)
    adr = int(self.model.sensor_adr[sid])
    return np.asarray(self.data.sensordata[adr : adr + dim], dtype=np.float32).copy()

  def _get_obs(self):
    # acc = self._sensor_vec("imu_acc", 3)
    # return acc

    x = self.data.qpos[self.model.jnt_qposadr[self.root_joint_id]]
    return x

  
