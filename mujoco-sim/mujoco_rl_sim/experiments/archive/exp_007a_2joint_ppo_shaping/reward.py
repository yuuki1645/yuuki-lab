"""exp_004 のステップ報酬（exp_003 前進 + exp_001 shaping）。

1 ステップの合計（env 適用前）::

  total = forward - effort_penalty + upright + knee_flex
          - backward_lean_penalty - height_penalty

終了ペナルティ（姿勢・接触）は termination.py → env.py で加算。
"""

from dataclasses import dataclass

import config
from effort import EffortBreakdown
from observation import StepPhysics


@dataclass(frozen=True)
class RewardBreakdown:
  """1 ステップ分の報酬の内訳。"""

  forward_imu: float
  forward_foot: float
  upright_bonus: float
  knee_flex_bonus: float
  backward_lean_penalty: float
  height_penalty: float
  effort_penalty: float
  effort_power_cost: float

  @property
  def forward(self) -> float:
    return self.forward_imu + self.forward_foot

  @property
  def shaping(self) -> float:
    """前進以外の shaping 合計（wandb 用）。"""
    return (
      self.upright_bonus
      + self.knee_flex_bonus
      - self.backward_lean_penalty
      - self.height_penalty
    )

  @property
  def total(self) -> float:
    return self.forward + self.shaping - self.effort_penalty


class Reward:
  """報酬のみ計算する（早期終了・時間切れの判定は Termination / train）。"""

  @staticmethod
  def _forward_component(
    dx: float,
    *,
    upright: float,
    foot_on_floor: bool,
  ) -> float:
    dx_clipped = max(-config.MAX_DX_PER_STEP, min(config.MAX_DX_PER_STEP, float(dx)))
    if upright < config.FORWARD_MIN_UPRIGHT:
      return 0.0
    if config.FORWARD_REQUIRE_FOOT_CONTACT and not foot_on_floor:
      return 0.0
    return max(0.0, dx_clipped) * config.FORWARD_REWARD_SCALE

  @staticmethod
  def _upright_bonus(upright: float) -> float:
    return (
      max(0.0, float(upright) - config.UPRIGHT_BONUS_THRESH)
      * config.UPRIGHT_BONUS_SCALE
    )

  @staticmethod
  def _knee_flex_bonus(knee_angle: float, *, upright: float) -> float:
    if upright < config.KNEE_FLEX_MIN_UPRIGHT:
      return 0.0
    if config.KNEE_HUMAN_FLEX_MIN_RAD <= knee_angle <= config.KNEE_HUMAN_FLEX_MAX_RAD:
      return config.KNEE_HUMAN_FLEX_BONUS_SCALE
    return 0.0

  @staticmethod
  def _backward_lean_penalty(imu_zaxis_x: float) -> float:
    excess = max(0.0, -float(imu_zaxis_x) - config.LEAN_BACKWARD_THRESH)
    return excess * config.LEAN_BACKWARD_PENALTY_SCALE

  @staticmethod
  def _height_penalty(imu_z: float) -> float:
    deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
    return deficit * config.IMU_HEIGHT_PENALTY_SCALE

  def compute(
    self,
    step_physics: StepPhysics,
    *,
    effort: EffortBreakdown,
  ) -> RewardBreakdown:
    upright = step_physics.upright
    foot_on_floor = step_physics.foot_on_floor

    forward_imu = self._forward_component(
      step_physics.dx, upright=upright, foot_on_floor=foot_on_floor
    )
    forward_foot = self._forward_component(
      step_physics.foot_dx, upright=upright, foot_on_floor=foot_on_floor
    )

    effort_penalty = effort.penalty if config.APPLY_EFFORT_PENALTY else 0.0

    return RewardBreakdown(
      forward_imu=forward_imu,
      forward_foot=forward_foot,
      upright_bonus=self._upright_bonus(upright),
      knee_flex_bonus=self._knee_flex_bonus(
        step_physics.knee_angle, upright=upright
      ),
      backward_lean_penalty=self._backward_lean_penalty(step_physics.imu_zaxis_x),
      height_penalty=self._height_penalty(step_physics.imu_z),
      effort_penalty=effort_penalty,
      effort_power_cost=effort.power_cost,
    )
