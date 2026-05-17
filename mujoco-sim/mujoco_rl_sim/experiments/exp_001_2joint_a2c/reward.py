from dataclasses import dataclass

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config


@dataclass(frozen=True)
class RewardBreakdown:
  forward: float
  upright: float
  knee_flex_bonus: float
  knee_wrong_penalty: float
  lean_penalty: float
  height_penalty: float

  @property
  def total(self) -> float:
    return (
      self.forward
      + self.upright
      + self.knee_flex_bonus
      - self.knee_wrong_penalty
      - self.lean_penalty
      - self.height_penalty
    )


class Reward:
  """報酬のみ計算する（終了判定は Termination）。"""

  def compute(
    self,
    *,
    dx: float,
    upright: float,
    knee_angle: float,
    foot_on_floor: bool,
    imu_z: float,
    imu_zaxis_x: float,
  ) -> RewardBreakdown:
    knee_wrong_excess = max(0.0, -knee_angle - config.KNEE_WRONG_THRESH_RAD)
    knee_wrong_penalty = knee_wrong_excess * config.KNEE_WRONG_PENALTY_SCALE

    knee_flex_bonus = 0.0
    if config.KNEE_HUMAN_FLEX_MIN_RAD <= knee_angle <= config.KNEE_HUMAN_FLEX_MAX_RAD:
      knee_flex_bonus = config.KNEE_HUMAN_FLEX_BONUS_SCALE

    dx_clipped = max(-config.MAX_DX_PER_STEP, min(config.MAX_DX_PER_STEP, float(dx)))

    forward = 0.0
    if upright >= config.FORWARD_MIN_UPRIGHT:
      if not config.FORWARD_REQUIRE_FOOT_CONTACT or foot_on_floor:
        forward = max(0.0, dx_clipped) * config.FORWARD_REWARD_SCALE

    upright_bonus = (
      max(0.0, upright - config.UPRIGHT_BONUS_THRESH) * config.UPRIGHT_BONUS_SCALE
    )

    lean_excess = max(0.0, -float(imu_zaxis_x) - config.LEAN_FORWARD_THRESH)
    lean_penalty = lean_excess * config.LEAN_FORWARD_PENALTY_SCALE

    height_deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
    height_penalty = height_deficit * config.IMU_HEIGHT_PENALTY_SCALE

    return RewardBreakdown(
      forward=forward,
      upright=upright_bonus,
      knee_flex_bonus=knee_flex_bonus,
      knee_wrong_penalty=knee_wrong_penalty,
      lean_penalty=lean_penalty,
      height_penalty=height_penalty,
    )
