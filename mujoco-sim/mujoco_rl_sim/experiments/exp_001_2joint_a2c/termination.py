from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config


class Termination:
  """エピソード終了（転倒・前傾しすぎ）判定。"""

  def is_done(
    self,
    *,
    imu_z: float,
    upright: float,
    imu_zaxis_x: float,
  ) -> bool:
    if imu_z < config.MIN_IMU_Z:
      return True
    if upright < config.MIN_IMU_UPRIGHT:
      return True
    if imu_zaxis_x < -config.MAX_FORWARD_LEAN:
      return True
    return False
