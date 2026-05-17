import time

import mujoco
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.debug import print_step_overlay
from mujoco_rl_sim.lib.ctrl import action_to_ctrl
from mujoco_rl_sim.lib.mujoco_paths import mujoco_sim_asset_path
from mujoco_rl_sim.lib.obs_norm import clip_scale, height_to_norm, range_to_norm


class EnvExp0012JointA2C:
  """007_leg_2joint 用 A2C 環境（exp_001）。"""

  def __init__(self, *, enable_viewer: bool = True):
    xml_path = mujoco_sim_asset_path(config.XML_PATH)
    self.model = mujoco.MjModel.from_xml_path(xml_path)
    apply_model_visual_preset(self.model)
    self.data = mujoco.MjData(self.model)

    self.viewer = None
    if enable_viewer:
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
    self._debug_step_counter = 0
    self.floor_id = self.model.geom("floor").id
    self.foot_id = self.model.geom("foot_plate").id

  def _imu_x(self) -> float:
    return float(self.data.site("imu_site").xpos[0])

  def _imu_z(self) -> float:
    return float(self.data.site("imu_site").xpos[2])

  def _capture_episode_origin(self) -> None:
    self._origin_imu_x = self._imu_x()
    self._prev_x = self._origin_imu_x

  def reset(self):
    mujoco.mj_resetData(self.model, self.data)
    mujoco.mj_forward(self.model, self.data)
    if self.viewer is not None:
      self.viewer.sync()
    self._capture_episode_origin()
    self._prev_action = (0.0, 0.0)
    return self._get_obs(reward=0.0, episode_step=0, dx=0.0)

  def step(self, action, visualize: bool = False, episode_step: int = 0):
    knee_a = max(-1.0, min(1.0, float(action[0])))
    ankle_a = max(-1.0, min(1.0, float(action[1])))

    self.data.ctrl[self.model.actuator("knee_servo").id] = action_to_ctrl(knee_a, self._knee_ctrl_range)
    self.data.ctrl[self.model.actuator("ankle_servo").id] = action_to_ctrl(ankle_a, self._ankle_ctrl_range)

    mujoco.mj_step(self.model, self.data)
    if self.viewer is not None:
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
    knee_wrong_excess = max(0.0, -knee_angle - config.KNEE_WRONG_THRESH_RAD)
    knee_wrong_penalty = knee_wrong_excess * config.KNEE_WRONG_PENALTY_SCALE

    knee_human_flex_bonus = 0.0
    if config.KNEE_HUMAN_FLEX_MIN_RAD <= knee_angle <= config.KNEE_HUMAN_FLEX_MAX_RAD:
      knee_human_flex_bonus = config.KNEE_HUMAN_FLEX_BONUS_SCALE

    terminated = imu_z < config.MIN_IMU_Z or upright < config.MIN_IMU_UPRIGHT

    reward = (
      dx * config.FORWARD_REWARD_SCALE
      + upright * config.UPRIGHT_BONUS_SCALE
      + knee_human_flex_bonus
      - knee_wrong_penalty
    )
    if terminated:
      reward += config.FALL_PENALTY

    self._prev_action = (knee_a, ankle_a)

    obs = self._get_obs(
      reward=reward,
      episode_step=episode_step,
      dx=dx,
      knee_angle=knee_angle,
      knee_wrong_penalty=knee_wrong_penalty,
      knee_human_flex_bonus=knee_human_flex_bonus,
    )
    return obs, reward, terminated

  def _get_obs(
    self,
    *,
    reward: float,
    episode_step: int = 0,
    dx: float = 0.0,
    knee_angle: float = 0.0,
    knee_wrong_penalty: float = 0.0,
    knee_human_flex_bonus: float = 0.0,
  ):
    imu_x = self._imu_x()
    imu_z = self._imu_z()
    rel_imu_x = imu_x - self._origin_imu_x

    foot_on_floor = False
    for i in range(self.data.ncon):
      c = self.data.contact[i]
      if (c.geom1 == self.foot_id and c.geom2 == self.floor_id) or (
        c.geom2 == self.foot_id and c.geom1 == self.floor_id
      ):
        foot_on_floor = True
        break

    imu_gyro = self.data.sensor("imu_gyro").data.copy()
    imu_gyro_x = float(imu_gyro[0])
    imu_gyro_y = float(imu_gyro[1])
    imu_gyro_z = float(imu_gyro[2])

    imu_zaxis = self.data.sensor("imu_zaxis").data.copy()
    imu_zaxis_x = float(imu_zaxis[0])
    imu_zaxis_y = float(imu_zaxis[1])
    imu_zaxis_z = float(imu_zaxis[2])

    foot_z = float(self.data.site("foot_site").xpos[2])
    foot_xaxis = self.data.sensor("foot_xaxis").data.copy()

    knee_angle = float(self.data.joint("knee").qpos[0])
    ankle_angle = float(self.data.joint("ankle").qpos[0])
    knee_vel = float(self.data.joint("knee").qvel[0])
    ankle_vel = float(self.data.joint("ankle").qvel[0])

    toe_pos = self.data.sensor("toe_pos").data.copy()
    com = self.data.subtree_com[self._basket_thigh_body_id]
    com_x = float(com[0] - toe_pos[0])
    com_z = float(com[2])

    if self._debug_step_counter == 100:
      self._debug_step_counter = 0
      print_step_overlay(
        episode_step=float(episode_step),
        reward=reward,
        knee_human_flex_bonus=knee_human_flex_bonus,
        knee_wrong_penalty=knee_wrong_penalty,
        foot_on_floor=foot_on_floor,
        imu_gyro_x=imu_gyro_x,
        imu_gyro_y=imu_gyro_y,
        imu_gyro_z=imu_gyro_z,
        imu_zaxis_x=imu_zaxis_x,
        imu_zaxis_y=imu_zaxis_y,
        imu_zaxis_z=imu_zaxis_z,
        imu_x=imu_x,
        rel_imu_x=rel_imu_x,
        dx=dx,
        imu_z=imu_z,
        foot_z=foot_z,
        foot_xaxis_z=float(foot_xaxis[2]),
        knee_angle=knee_angle,
        ankle_angle=ankle_angle,
        knee_vel=knee_vel,
        ankle_vel=ankle_vel,
        com_x=com_x,
        com_z=com_z,
        prev_knee_action=self._prev_action[0],
        prev_ankle_action=self._prev_action[1],
      )

    self._debug_step_counter += 1

    z_min = config.MIN_IMU_Z_NORM
    z_max = config.MAX_IMU_Z

    return (
      clip_scale(rel_imu_x, config.MAX_REL_IMU_X),
      clip_scale(dx, config.MAX_DX_PER_STEP),
      1.0 if foot_on_floor else -1.0,
      clip_scale(imu_gyro_x, config.MAX_GYRO_RAD_S),
      clip_scale(imu_gyro_y, config.MAX_GYRO_RAD_S),
      clip_scale(imu_gyro_z, config.MAX_GYRO_RAD_S),
      imu_zaxis_x,
      imu_zaxis_y,
      imu_zaxis_z,
      height_to_norm(imu_z, z_min, z_max),
      height_to_norm(foot_z, z_min, z_max),
      float(foot_xaxis[2]),
      range_to_norm(knee_angle, self._knee_q_range[0], self._knee_q_range[1]),
      range_to_norm(ankle_angle, self._ankle_q_range[0], self._ankle_q_range[1]),
      clip_scale(knee_vel, config.MAX_JOINT_VEL_RAD_S),
      clip_scale(ankle_vel, config.MAX_JOINT_VEL_RAD_S),
      clip_scale(com_x, config.MAX_COM_X_OFFSET),
      height_to_norm(com_z, z_min, z_max),
      float(self._prev_action[0]),
      float(self._prev_action[1]),
    )


# 旧名（010）との互換
Env010A2C = EnvExp0012JointA2C
