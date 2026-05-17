from dataclasses import dataclass

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config


@dataclass(frozen=True)
class RewardBreakdown:
  forward: float
  upright: float
  knee_flex_bonus: float
  knee_wrong_penalty: float

  @property
  def total(self) -> float:
    return (
      self.forward
      + self.upright
      + self.knee_flex_bonus
      - self.knee_wrong_penalty
    )


class Reward:
  """報酬のみ計算する（終了判定は Termination）。"""

  def compute(
    self,
    *,
    dx: float,
    upright: float,
    knee_angle: float,
  ) -> RewardBreakdown:
    knee_wrong_excess = max(0.0, -knee_angle - config.KNEE_WRONG_THRESH_RAD)
    knee_wrong_penalty = knee_wrong_excess * config.KNEE_WRONG_PENALTY_SCALE

    knee_flex_bonus = 0.0
    if config.KNEE_HUMAN_FLEX_MIN_RAD <= knee_angle <= config.KNEE_HUMAN_FLEX_MAX_RAD:
      knee_flex_bonus = config.KNEE_HUMAN_FLEX_BONUS_SCALE

    return RewardBreakdown(
      forward=dx * config.FORWARD_REWARD_SCALE,
      upright=upright * config.UPRIGHT_BONUS_SCALE,
      knee_flex_bonus=knee_flex_bonus,
      knee_wrong_penalty=knee_wrong_penalty,
    )
