import mujoco
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

import time


class Env009A2C:
  """007_leg_2joint 用 A2C 環境。

  観測（9）: knee 角度, ankle 角度, imu_site の z, imu_zaxis (x,y,z), foot_zaxis (x,y,z)
  行動（2）: [-1, 1] を knee_servo / ankle_servo の目標角 [rad] にスケール
  """

  def __init__(self):
    self.model = mujoco.MjModel.from_xml_path("../../mujoco_sim_assets/xmls/007_leg_2joint/main.xml")
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)
    self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
    apply_passive_viewer_options(self.viewer)

    # main.xml の ctrlrange に合わせる（±π/2）
    self._max_ctrl_rad = 1.571

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    self.viewer.sync()
    return self._get_obs()

  def step(self, action, visualize=False):
    knee_a, ankle_a = action
    knee_a = max(-1.0, min(1.0, float(knee_a)))
    ankle_a = max(-1.0, min(1.0, float(ankle_a)))

    self.data.ctrl[0] = knee_a * self._max_ctrl_rad
    self.data.ctrl[1] = ankle_a * self._max_ctrl_rad

    mujoco.mj_step(self.model, self.data)
    self.viewer.sync()

    if visualize:
      time.sleep(self.model.opt.timestep)

    obs_next = self._get_obs()

    x = self.data.site("imu_site").xpos[0]
    z = self.data.site("imu_site").xpos[2]
    print(f"x: {x: 8.3f} | z: {z: 8.3f}")

    # reward = self.data.site("imu_site").xpos[0]
    reward = x * 0.1 + z * 0.1

    return obs_next, reward

  def _get_obs(self):
    knee_angle = self.data.joint("knee").qpos[0]
    ankle_angle = self.data.joint("ankle").qpos[0]
    imu_z = self.data.site("imu_site").xpos[2]
    imu_zaxis = self.data.sensor("imu_zaxis").data.copy()
    foot_zaxis = self.data.sensor("foot_zaxis").data.copy()

    return (
      float(knee_angle),
      float(ankle_angle),
      float(imu_z),
      float(imu_zaxis[0]),
      float(imu_zaxis[1]),
      float(imu_zaxis[2]),
      float(foot_zaxis[0]),
      float(foot_zaxis[1]),
      float(foot_zaxis[2]),
    )
