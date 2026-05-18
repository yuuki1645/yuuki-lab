from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config

REASON_IMU_Z = "imu_z"
REASON_LOW_UPRIGHT = "low_upright"
REASON_FORWARD_LEAN = "forward_lean"
REASON_TRUNCATED = "truncated"

TERMINATION_REASONS = (
  REASON_IMU_Z,
  REASON_LOW_UPRIGHT,
  REASON_FORWARD_LEAN,
  REASON_TRUNCATED,
)


class Termination:
  """エピソード終了（転倒・前傾しすぎ）判定。"""

  def done_reason(
    self,
    *,
    imu_z: float,
    upright: float,
    imu_zaxis_x: float,
  ) -> str | None:
    """最初に満たした終了条件の識別子。終了しない場合は None。"""
    if imu_z < config.MIN_IMU_Z:
      return REASON_IMU_Z
    if upright < config.MIN_IMU_UPRIGHT:
      return REASON_LOW_UPRIGHT
    if imu_zaxis_x < -config.MAX_FORWARD_LEAN:
      return REASON_FORWARD_LEAN
    return None

  def is_done(
    self,
    *,
    imu_z: float,
    upright: float,
    imu_zaxis_x: float,
  ) -> bool:
    return self.done_reason(
      imu_z=imu_z,
      upright=upright,
      imu_zaxis_x=imu_zaxis_x,
    ) is not None
