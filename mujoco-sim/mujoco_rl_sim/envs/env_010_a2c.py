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

# 膝ヒンジ +Y: qpos>0 は前折れ（くの字）、qpos<0 は人間と同じ後方屈曲
KNEE_FORWARD_THRESH_RAD = 0.05
KNEE_FORWARD_PENALTY_SCALE = 5.0
KNEE_HUMAN_FLEX_MIN_RAD = -1.2
KNEE_HUMAN_FLEX_MAX_RAD = -0.02
KNEE_BACKWARD_BONUS_SCALE = 0.15


def _knee_angle_to_logical_deg(knee_angle: float) -> float:
  return math.degrees(knee_angle)

def _ankle_angle_to_logical_deg(ankle_angle: float) -> float:
  return math.degrees(ankle_angle)

def bar(min_value: float, max_value: float, value: float):
  rate = (value - min_value) / (max_value - min_value)
  bar_length = 20
  filled_length = int(bar_length * rate)

  if filled_length < 0:
    filled_length = 0
  if filled_length > bar_length:
    filled_length = bar_length
  
  # bar = f"({min_value: 4.1f}) [" + "█" * filled_length + " " * (bar_length - filled_length) + f"] ({max_value: 4.1f})"
  bar = f"[" + "█" * filled_length + " " * (bar_length - filled_length) + f"] ({min_value:.1f} -- {max_value:.1f})"

  if rate < 0.0:
    bar += " (<<<)"
  if rate > 1.0:
    bar += " (   >>>)"
  
  return bar


class Env010A2C:
  """007_leg_2joint 用 A2C 環境。

  観測（20）: imu_x, dx, foot_on_floor, imu_gyro (3), imu_zaxis (3), imu_z, foot_z,
              foot_xaxis[2], knee/ankle [deg], knee/ankle vel [rad/s], com_x, com_z,
              prev_knee/ankle 指令（[-1,1]）
  行動（2）: [-1, 1] を knee_servo / ankle_servo の目標角 [rad] にスケール
  報酬: dx 前進 + 直立 + 膝後方屈曲ボーナス − 膝前折れペナルティ。転倒で終了。
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
    self._prev_action = (0.0, 0.0)

    self.count = 0

    self.floor_id = self.model.geom("floor").id
    self.foot_id = self.model.geom("foot_plate").id

  def _imu_x(self):
    return float(self.data.site("imu_site").xpos[0])

  def _imu_z(self):
    return float(self.data.site("imu_site").xpos[2])

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    self.viewer.sync()
    self._prev_x = self._imu_x()
    self._prev_action = (0.0, 0.0)
    return self._get_obs(0.0, episode_step=0, dx=0.0)

  def step(self, action, visualize=False, episode_step=0):
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

    knee_angle = float(self.data.joint("knee").qpos[0])
    knee_forward_excess = max(0.0, knee_angle - KNEE_FORWARD_THRESH_RAD)
    knee_forward_penalty = knee_forward_excess * KNEE_FORWARD_PENALTY_SCALE

    knee_backward_bonus = 0.0
    if KNEE_HUMAN_FLEX_MIN_RAD <= knee_angle <= KNEE_HUMAN_FLEX_MAX_RAD:
      knee_backward_bonus = KNEE_BACKWARD_BONUS_SCALE

    terminated = imu_z < MIN_IMU_Z or upright < MIN_IMU_UPRIGHT
    # terminated = imu_z < MIN_IMU_Z
    # terminated = False

    # reward = dx * FORWARD_REWARD_SCALE + upright * UPRIGHT_BONUS_SCALE
    # reward = x * 1.0 + upright * UPRIGHT_BONUS_SCALE
    # reward = x * 1.0 + imu_z * 1.0
    reward = (
      dx * FORWARD_REWARD_SCALE
      + upright * UPRIGHT_BONUS_SCALE
      + knee_backward_bonus
      - knee_forward_penalty
    )

    if terminated:
      reward += FALL_PENALTY

    self._prev_action = (knee_a, ankle_a)

    return self._get_obs(
      reward,
      episode_step,
      dx=dx,
      knee_angle=knee_angle,
      knee_forward_penalty=knee_forward_penalty,
      knee_backward_bonus=knee_backward_bonus,
    ), reward, terminated

  def _get_obs(
    self,
    reward,
    episode_step=0,
    dx=0.0,
    knee_angle=0.0,
    knee_forward_penalty=0.0,
    knee_backward_bonus=0.0,
  ):
    imu_x = self._imu_x()
    imu_z = self._imu_z()

    # 足裏が床に接触しているかどうか
    n = self.data.ncon
    foot_on_floor = False
    for i in range(n):
      c = self.data.contact[i]
      if (c.geom1 == self.foot_id and c.geom2 == self.floor_id) or (c.geom2 == self.foot_id and c.geom1 == self.floor_id):
        foot_on_floor = True
        break

    # [IMU Gyro] (rad/s)
    imu_gyro = self.data.sensor("imu_gyro").data.copy()
    imu_gyro_x = float(imu_gyro[0])
    imu_gyro_y = float(imu_gyro[1])
    imu_gyro_z = float(imu_gyro[2])

    # [IMU Z-axis]
    imu_zaxis = self.data.sensor("imu_zaxis").data.copy()
    imu_zaxis_x = float(imu_zaxis[0])
    imu_zaxis_y = float(imu_zaxis[1])
    imu_zaxis_z = float(imu_zaxis[2])

    foot_z = float(self.data.site("foot_site").xpos[2])
    foot_xaxis = self.data.sensor("foot_xaxis").data.copy()

    knee_angle = float(self.data.joint("knee").qpos[0])
    ankle_angle = self.data.joint("ankle").qpos[0]
    
    knee_vel = self.data.joint("knee").qvel[0]    # [rad/s]
    ankle_vel = self.data.joint("ankle").qvel[0]  # [rad/s]
    
    toe_pos = self.data.sensor("toe_pos").data.copy()
    com = self.data.subtree_com[self._basket_thigh_body_id]
    com_x = com[0] - toe_pos[0]
    com_z = com[2]

    knee_angle_logical = _knee_angle_to_logical_deg(knee_angle)
    ankle_angle_logical = _ankle_angle_to_logical_deg(ankle_angle)

    if self.count == 100:
      self.count = 0

      print(
        f"\033[2K\n"

        f"\033[2K[Episode Step]\n"
        f"\033[2K  step       : {episode_step: 8.3f}\n"

        f"\033[2K\n"

        f"\033[2K[Reward]\n"
        f"\033[2K  reward     : {reward: 8.3f}\n"
        f"\033[2K  knee_back  : {knee_backward_bonus: 8.3f}\n"
        f"\033[2K  knee_fwd-  : {knee_forward_penalty: 8.3f}\n"

        f"\033[2K\n"

        f"\033[2K[Foot on Floor]\n"
        f"\033[2K  flag       :    {int(foot_on_floor)}\n"

        f"\033[2K\n"

        f"\033[2K[IMU Gyro] (rad/s)\n"
        f"\033[2K  x          : {imu_gyro_x: 8.3f} {bar(-10.0, 10.0, imu_gyro_x)}\n"
        f"\033[2K  y          : {imu_gyro_y: 8.3f} {bar(-10.0, 10.0, imu_gyro_y)}\n"
        f"\033[2K  z          : {imu_gyro_z: 8.3f} {bar(-10.0, 10.0, imu_gyro_z)}\n"

        f"\033[2K\n"

        f"\033[2K[IMU Z-axis]\n"
        f"\033[2K  x          : {imu_zaxis_x: 8.3f} {bar(-1.0, 1.0, imu_zaxis_x)}\n"
        f"\033[2K  y          : {imu_zaxis_y: 8.3f} {bar(-1.0, 1.0, imu_zaxis_y)}\n"
        f"\033[2K  z          : {imu_zaxis_z: 8.3f} {bar(-1.0, 1.0, imu_zaxis_z)}\n"

        f"\033[2K\n"

        f"\033[2K[IMU Position]\n"
        f"\033[2K  imu_x      : {imu_x: 8.3f} {bar(-5.0, 5.0, imu_x)}\n"
        f"\033[2K  dx         : {dx: 8.3f} {bar(-0.05, 0.05, dx)}\n"
        f"\033[2K  imu_z      : {imu_z: 8.3f} {bar(0.0, 1.0, imu_z)}\n"

        f"\033[2K\n"

        f"\033[2Kfoot_z       : {foot_z: 8.3f} {bar(0.0, 1.0, foot_z)}\n"
        f"\033[2Kfoot_xaxis_x : {foot_xaxis[2]: 8.3f} {bar(-1.0, 1.0, foot_xaxis[2])}\n"
        
        f"\033[2K[Joints]\n"
        f"\033[2K  knee       : {knee_angle_logical: 6.1f}°  ({knee_angle: 8.3f}) {bar(-180.0, 180.0, knee_angle_logical)}\n"
        f"\033[2K  ankle      : {ankle_angle_logical: 6.1f}°  ({ankle_angle: 8.3f}) {bar(-180.0, 180.0, ankle_angle_logical)}\n"

        f"\033[2K\n"
        
        f"\033[2K[Joints Vel]\n"
        f"\033[2K  knee vel   : {knee_vel: 8.3f} {bar(-10.0, 10.0, knee_vel)}\n"
        f"\033[2K  ankle vel  : {ankle_vel: 8.3f} {bar(-10.0, 10.0, ankle_vel)}\n"
        
        f"\033[2K\n"

        f"\033[2K[COM]\n"        
        f"\033[2K  com_x      : {com_x: 8.3f} {bar(-1.0, 1.0, com_x)}\n"
        f"\033[2K  com_z      : {com_z: 8.3f} {bar(0.0, 1.0, com_z)}\n"

        f"\033[2K\n"

        f"\033[2K[Prev Action]\n"
        f"\033[2K  knee       : {self._prev_action[0]: 8.3f} {bar(-1.0, 1.0, self._prev_action[0])}\n"
        f"\033[2K  ankle      : {self._prev_action[1]: 8.3f} {bar(-1.0, 1.0, self._prev_action[1])}\033[43A\r"
      , end="")
    
    self.count += 1

    return (
      imu_x,
      float(dx),
      float(foot_on_floor),
      imu_gyro_x,
      imu_gyro_y,
      imu_gyro_z,
      imu_zaxis_x,
      imu_zaxis_y,
      imu_zaxis_z,
      imu_z,
      foot_z,
      float(foot_xaxis[2]),
      float(knee_angle_logical),
      float(ankle_angle_logical),
      float(knee_vel),
      float(ankle_vel),
      float(com_x),
      float(com_z),
      float(self._prev_action[0]),
      float(self._prev_action[1]),
    )
