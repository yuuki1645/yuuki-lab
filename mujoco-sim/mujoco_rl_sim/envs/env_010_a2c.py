import math

import mujoco
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

import time


# 前進は imu_site のワールド +x（足先 foot_site も +x 側）
FORWARD_REWARD_SCALE = 100.0
UPRIGHT_BONUS_SCALE = 0.05
FALL_PENALTY = -2.0
MIN_IMU_Z = 0.35
MIN_IMU_UPRIGHT = 0.35


def _knee_angle_to_logical_deg(knee_angle: float) -> float:
  return math.degrees(knee_angle)

def _ankle_angle_to_logical_deg(ankle_angle: float) -> float:
  return math.degrees(ankle_angle)

def bar(min_value: float, max_value: float, value: float):
  rate = (value - min_value) / (max_value - min_value)
  bar_length = 20
  filled_length = int(bar_length * rate)

  if filled_length > bar_length:
    filled_length = bar_length
  
  # bar = f"({min_value: 4.1f}) [" + "█" * filled_length + " " * (bar_length - filled_length) + f"] ({max_value: 4.1f})"
  bar = f"[" + "█" * filled_length + " " * (bar_length - filled_length) + f"] ({min_value:.1f} -- {max_value:.1f})"

  if rate > 1.0:
    bar += " (over)"
  
  return bar


class Env010A2C:
  """007_leg_2joint 用 A2C 環境。

  観測（7）: imu_z, foot_z, foot_xaxis[2], knee [deg], ankle [deg], com_x, com_z
  行動（2）: [-1, 1] を knee_servo / ankle_servo の目標角 [rad] にスケール
  報酬: 1 ステップあたりの +x 変位（前進）＋弱い直立ボーナス。転倒で終了。
  """

  def __init__(self):
    self.model = mujoco.MjModel.from_xml_path("../../mujoco_sim_assets/xmls/007_leg_2joint/main.xml")
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)
    self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
    apply_passive_viewer_options(self.viewer)

    self._basket_thigh_body_id = self.model.body("basket_thigh").id
    self._max_ctrl_rad = 1.571
    self._prev_x = 0.0

    self.count = 0

  def _imu_x(self):
    return float(self.data.site("imu_site").xpos[0])

  def _imu_z(self):
    return float(self.data.site("imu_site").xpos[2])

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    self.viewer.sync()
    self._prev_x = self._imu_x()
    return self._get_obs()

  def step(self, action, visualize=False):
    knee_a = max(-1.0, min(1.0, float(action[0])))
    ankle_a = max(-1.0, min(1.0, float(action[1])))

    self.data.ctrl[0] = knee_a * self._max_ctrl_rad
    self.data.ctrl[1] = ankle_a * self._max_ctrl_rad

    mujoco.mj_step(self.model, self.data)
    self.viewer.sync()

    if visualize:
      time.sleep(self.model.opt.timestep)

    x = self._imu_x()
    dx = x - self._prev_x
    self._prev_x = x

    imu_zaxis = self.data.sensor("imu_zaxis").data.copy()
    upright = float(imu_zaxis[2])
    imu_z = self._imu_z()

    # terminated = imu_z < MIN_IMU_Z or upright < MIN_IMU_UPRIGHT
    terminated = imu_z < MIN_IMU_Z

    # reward = dx * FORWARD_REWARD_SCALE + upright * UPRIGHT_BONUS_SCALE
    reward = x * 0.1 + upright * UPRIGHT_BONUS_SCALE
    if terminated:
      reward += FALL_PENALTY

    return self._get_obs(), reward, terminated

  def _get_obs(self):
    imu_z = self._imu_z()
    foot_z = float(self.data.site("foot_site").xpos[2])
    foot_xaxis = self.data.sensor("foot_xaxis").data.copy()
    knee_angle = self.data.joint("knee").qpos[0]
    ankle_angle = self.data.joint("ankle").qpos[0]
    toe_pos = self.data.sensor("toe_pos").data.copy()
    com = self.data.subtree_com[self._basket_thigh_body_id]
    com_x = com[0] - toe_pos[0]
    com_z = com[2]

    knee_angle_logical = _knee_angle_to_logical_deg(knee_angle)
    ankle_angle_logical = _ankle_angle_to_logical_deg(ankle_angle)

    if self.count == 100:
      self.count = 0

      print(
        f"\033[2Kimu_z        : {imu_z: 8.3f} {bar(0.0, 1.0, imu_z)}\n"
        f"\033[2Kfoot_z       : {foot_z: 8.3f} {bar(0.0, 1.0, foot_z)}\n"
        f"\033[2Kfoot_xaxis_x : {foot_xaxis[2]: 8.3f} {bar(-1.0, 1.0, foot_xaxis[2])}\n"
        f"\033[2Kknee         : {knee_angle_logical: 6.1f}°  ({knee_angle: 8.3f}) {bar(-180.0, 180.0, knee_angle_logical)}\n"
        f"\033[2Kankle        : {ankle_angle_logical: 6.1f}°  ({ankle_angle: 8.3f}) {bar(-180.0, 180.0, ankle_angle_logical)}\n"
        f"\033[2Kcom_x        : {com_x: 8.3f} {bar(-1.0, 1.0, com_x)}\n"
        f"\033[2Kcom_z        : {com_z: 8.3f} {bar(0.0, 1.0, com_z)}\033[6A\r"
      , end="")
    
    self.count += 1

    return (
      imu_z,
      foot_z,
      float(foot_xaxis[2]),
      float(math.degrees(knee_angle)),
      float(math.degrees(ankle_angle)),
      float(com_x),
      float(com_z),
    )
