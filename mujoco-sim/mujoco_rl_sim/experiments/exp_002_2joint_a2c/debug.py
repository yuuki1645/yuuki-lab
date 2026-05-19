import math

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.lib.terminal_bar import terminal_bar


def _deg(rad: float) -> float:
  return math.degrees(rad)


def print_step_overlay(
  *,
  episode_step: float,
  reward: float,
  foot_on_floor: bool,
  imu_gyro_x: float,
  imu_gyro_y: float,
  imu_gyro_z: float,
  imu_zaxis_x: float,
  imu_zaxis_y: float,
  imu_zaxis_z: float,
  imu_x: float,
  rel_imu_x: float,
  dx: float,
  imu_z: float,
  foot_z: float,
  foot_xaxis_z: float,
  knee_angle: float,
  ankle_angle: float,
  knee_vel: float,
  ankle_vel: float,
  com_x: float,
  com_z: float,
  prev_knee_action: float,
  prev_ankle_action: float,
) -> None:
  bar = terminal_bar
  knee_deg = _deg(knee_angle)
  ankle_deg = _deg(ankle_angle)

  print(
    f"\033[2K\n"
    f"\033[2K[Episode Step]\n"
    f"\033[2K  step       : {episode_step: 8.3f}\n"
    f"\033[2K\n"
    f"\033[2K[Reward]\n"
    f"\033[2K  reward     : {reward: 8.3f}\n"
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
    f"\033[2K  imu_x      : {imu_x: 8.3f} (rel {rel_imu_x: 8.3f}) {bar(-5.0, 5.0, imu_x)}\n"
    f"\033[2K  dx         : {dx: 8.3f} {bar(-config.MAX_DX_PER_STEP, config.MAX_DX_PER_STEP, dx)}\n"
    f"\033[2K  imu_z      : {imu_z: 8.3f} {bar(0.0, 1.0, imu_z)}\n"
    f"\033[2K\n"
    f"\033[2Kfoot_z       : {foot_z: 8.3f} {bar(0.0, 1.0, foot_z)}\n"
    f"\033[2Kfoot_xaxis_x : {foot_xaxis_z: 8.3f} {bar(-1.0, 1.0, foot_xaxis_z)}\n"
    f"\033[2K[Joints]\n"
    f"\033[2K  knee       : {knee_deg: 6.1f}°  ({knee_angle: 8.3f}) {bar(-180.0, 180.0, knee_deg)}\n"
    f"\033[2K  ankle      : {ankle_deg: 6.1f}°  ({ankle_angle: 8.3f}) {bar(-180.0, 180.0, ankle_deg)}\n"
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
    f"\033[2K  knee       : {prev_knee_action: 8.3f} {bar(-1.0, 1.0, prev_knee_action)}\n"
    f"\033[2K  ankle      : {prev_ankle_action: 8.3f} {bar(-1.0, 1.0, prev_ankle_action)}\033[43A\r",
    end="",
  )
