import math

import mujoco
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

import time


# 前進は imu_site のワールド +x（足先 foot_site も +x 側）
# FORWARD_REWARD_SCALE = 100.0
FORWARD_REWARD_SCALE = 500.0
UPRIGHT_BONUS_SCALE = 0.05
FALL_PENALTY = -10.0
MIN_IMU_Z = 0.35
MIN_IMU_UPRIGHT = 0.35

# 膝ヒンジ +Y: ctrl/qpos>0 が人間と同じ後方屈曲（良い）、負側が反対向き
KNEE_WRONG_THRESH_RAD = 0.05
KNEE_WRONG_PENALTY_SCALE = 5.0
KNEE_HUMAN_FLEX_MIN_RAD = 0.02
KNEE_HUMAN_FLEX_MAX_RAD = 1.2
KNEE_HUMAN_FLEX_BONUS_SCALE = 0.15

# 観測正規化（おおよそ [-1, 1]）。スケールはモデル・歩行のオーダーから見積もり。
MAX_REL_IMU_X = 2.0
MAX_DX_PER_STEP = 0.05
MAX_GYRO_RAD_S = 10.0
MAX_JOINT_VEL_RAD_S = 10.0
MAX_COM_X_OFFSET = 0.6
MAX_IMU_Z = 1.2
MIN_IMU_Z_NORM = 0.0


def _clip_scale(value: float, scale: float) -> float:
  if scale <= 0.0:
    return 0.0
  return max(-1.0, min(1.0, float(value) / scale))


def _range_to_norm(value: float, lo: float, hi: float) -> float:
  if hi <= lo:
    return 0.0
  t = (float(value) - lo) / (hi - lo)
  return max(-1.0, min(1.0, 2.0 * t - 1.0))


def _height_to_norm(z: float) -> float:
  span = MAX_IMU_Z - MIN_IMU_Z_NORM
  if span <= 0.0:
    return 0.0
  t = (float(z) - MIN_IMU_Z_NORM) / span
  return max(-1.0, min(1.0, 2.0 * t - 1.0))


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

  観測（20）: すべておおよそ [-1, 1]（関節角は qpos [rad] を joint range で正規化）。
              rel_imu_x, dx, foot_on_floor, imu_gyro (3), imu_zaxis (3), imu_z, foot_z,
              foot_xaxis[2], knee/ankle, knee/ankle vel, com_x, com_z, prev_action (2)
  行動（2）: [-1, 1] を各 actuator の ctrlrange（XML）内の目標角 [rad] に線形マッピング
  報酬: dx 前進 + 直立 + 膝屈曲（ctrl+ 側）ボーナス − 反対向きペナルティ。転倒で終了。
  """

  def __init__(self):
    self.model = mujoco.MjModel.from_xml_path("../../mujoco_sim_assets/xmls/007_leg_2joint/main.xml")
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)
    self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
    apply_passive_viewer_options(self.viewer)

    self._basket_thigh_body_id = self.model.body("basket_thigh").id
    self._knee_ctrl_range = self.model.actuator_ctrlrange[self.model.actuator("knee_servo").id].copy()
    self._ankle_ctrl_range = self.model.actuator_ctrlrange[self.model.actuator("ankle_servo").id].copy()
    self._knee_q_range = self.model.jnt_range[self.model.joint("knee").id].copy()
    self._ankle_q_range = self.model.jnt_range[self.model.joint("ankle").id].copy()
    self._origin_imu_x = 0.0
    self._prev_x = 0.0
    self._prev_action = (0.0, 0.0)

    self.count = 0

    self.floor_id = self.model.geom("floor").id
    self.foot_id = self.model.geom("foot_plate").id

  @staticmethod
  def _action_to_ctrl(action_val: float, ctrl_range) -> float:
    """[-1, 1] を ctrlrange [min, max] に線形マッピングする。"""
    a = max(-1.0, min(1.0, float(action_val)))
    lo, hi = float(ctrl_range[0]), float(ctrl_range[1])
    return lo + (a + 1.0) * 0.5 * (hi - lo)

  def _imu_x(self):
    return float(self.data.site("imu_site").xpos[0])

  def _imu_z(self):
    return float(self.data.site("imu_site").xpos[2])

  def _capture_episode_origin(self):
    self._origin_imu_x = self._imu_x()
    self._prev_x = self._origin_imu_x

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    self.viewer.sync()
    self._capture_episode_origin()
    self._prev_action = (0.0, 0.0)
    return self._get_obs(0.0, episode_step=0, dx=0.0)

  def step(self, action, visualize=False, episode_step=0):
    knee_a = max(-1.0, min(1.0, float(action[0])))
    ankle_a = max(-1.0, min(1.0, float(action[1])))

    self.data.ctrl[self.model.actuator("knee_servo").id] = self._action_to_ctrl(knee_a, self._knee_ctrl_range)
    self.data.ctrl[self.model.actuator("ankle_servo").id] = self._action_to_ctrl(ankle_a, self._ankle_ctrl_range)

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
    knee_wrong_excess = max(0.0, -knee_angle - KNEE_WRONG_THRESH_RAD)
    knee_wrong_penalty = knee_wrong_excess * KNEE_WRONG_PENALTY_SCALE

    knee_human_flex_bonus = 0.0
    if KNEE_HUMAN_FLEX_MIN_RAD <= knee_angle <= KNEE_HUMAN_FLEX_MAX_RAD:
      knee_human_flex_bonus = KNEE_HUMAN_FLEX_BONUS_SCALE

    terminated = imu_z < MIN_IMU_Z or upright < MIN_IMU_UPRIGHT
    # terminated = imu_z < MIN_IMU_Z
    # terminated = False

    # reward = dx * FORWARD_REWARD_SCALE + upright * UPRIGHT_BONUS_SCALE
    # reward = x * 1.0 + upright * UPRIGHT_BONUS_SCALE
    # reward = x * 1.0 + imu_z * 1.0
    reward = (
      dx * FORWARD_REWARD_SCALE
      + upright * UPRIGHT_BONUS_SCALE
      + knee_human_flex_bonus
      - knee_wrong_penalty
    )

    if terminated:
      reward += FALL_PENALTY

    self._prev_action = (knee_a, ankle_a)

    return self._get_obs(
      reward,
      episode_step,
      dx=dx,
      knee_angle=knee_angle,
      knee_wrong_penalty=knee_wrong_penalty,
      knee_human_flex_bonus=knee_human_flex_bonus,
    ), reward, terminated

  def _get_obs(
    self,
    reward,
    episode_step=0,
    dx=0.0,
    knee_angle=0.0,
    knee_wrong_penalty=0.0,
    knee_human_flex_bonus=0.0,
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
        f"\033[2K  knee_flex+ : {knee_human_flex_bonus: 8.3f}\n"
        f"\033[2K  knee_wrong : {knee_wrong_penalty: 8.3f}\n"

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
        f"\033[2K  imu_x      : {imu_x: 8.3f} (rel {imu_x - self._origin_imu_x: 8.3f}) {bar(-5.0, 5.0, imu_x)}\n"
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

    rel_imu_x = imu_x - self._origin_imu_x

    return (
      _clip_scale(rel_imu_x, MAX_REL_IMU_X),
      _clip_scale(dx, MAX_DX_PER_STEP),
      1.0 if foot_on_floor else -1.0,
      _clip_scale(imu_gyro_x, MAX_GYRO_RAD_S),
      _clip_scale(imu_gyro_y, MAX_GYRO_RAD_S),
      _clip_scale(imu_gyro_z, MAX_GYRO_RAD_S),
      imu_zaxis_x,
      imu_zaxis_y,
      imu_zaxis_z,
      _height_to_norm(imu_z),
      _height_to_norm(foot_z),
      float(foot_xaxis[2]),
      _range_to_norm(knee_angle, self._knee_q_range[0], self._knee_q_range[1]),
      _range_to_norm(ankle_angle, self._ankle_q_range[0], self._ankle_q_range[1]),
      _clip_scale(knee_vel, MAX_JOINT_VEL_RAD_S),
      _clip_scale(ankle_vel, MAX_JOINT_VEL_RAD_S),
      _clip_scale(com_x, MAX_COM_X_OFFSET),
      _height_to_norm(com_z),
      float(self._prev_action[0]),
      float(self._prev_action[1]),
    )
