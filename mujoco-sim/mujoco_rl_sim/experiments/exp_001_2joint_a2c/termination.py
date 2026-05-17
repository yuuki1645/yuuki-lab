from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config


class Termination:
  """エピソード終了（転倒）判定。"""

  def is_done(self, *, imu_z: float, upright: float) -> bool:
    return imu_z < config.MIN_IMU_Z or upright < config.MIN_IMU_UPRIGHT
