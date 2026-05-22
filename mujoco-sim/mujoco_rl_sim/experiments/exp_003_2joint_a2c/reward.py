"""exp_003 のステップ報酬。

設計の狙い
---------
2 関節脚で「前に進む」ことを学習させるが、単純に IMU のワールド +X 変位 (dx) だけを
与えると、体を前に倒して IMU が進むだけでも高報酬になる（前倒れハック）。
そのため次を組み合わせる。

  1. 前進報酬 … 直立かつ足接地など条件を満たすときだけ dx / foot_dx を加点
  2. 筋負荷ペナルティ … |τ·q̇| を正規化して積分（effort.py / env の mj_step ループ）
     config.APPLY_EFFORT_PENALTY=False のときは報酬に反映しない（計測のみ）
  3. 終了ペナルティ … env.py で termination.done_reason の penalty を一度だけ加算

1 ステップの合計（env 適用前）::

  total = forward - effort_penalty

係数は config.py。終了判定は termination.py。
"""

from dataclasses import dataclass

from . import config
from .effort import EffortBreakdown
from .observation import StepPhysics


@dataclass(frozen=True)
class RewardBreakdown:
  """1 ステップ分の報酬の内訳。wandb の episode/forward_reward_sum などの元になる。"""

  forward_imu: float
  forward_foot: float
  effort_penalty: float
  effort_power_cost: float

  @property
  def forward(self) -> float:
    return self.forward_imu + self.forward_foot

  @property
  def total(self) -> float:
    return self.forward - self.effort_penalty


class Reward:
  """報酬のみ計算する（早期終了・時間切れの判定は Termination / train）。"""

  @staticmethod
  def _forward_component(
    dx: float,
    *,
    upright: float,
    foot_on_floor: bool,
  ) -> float:
    """条件付き前進報酬の 1 成分（imu dx または foot_site dx）。"""
    dx_clipped = max(-config.MAX_DX_PER_STEP, min(config.MAX_DX_PER_STEP, float(dx)))
    if upright < config.FORWARD_MIN_UPRIGHT:
      return 0.0
    if config.FORWARD_REQUIRE_FOOT_CONTACT and not foot_on_floor:
      return 0.0
    return max(0.0, dx_clipped) * config.FORWARD_REWARD_SCALE

  def compute(
    self,
    step_physics: StepPhysics,
    *,
    effort: EffortBreakdown,
  ) -> RewardBreakdown:
    """1 環境ステップ分の報酬内訳を返す。

    step_physics
        observation.build が返す当ステップの物理量（正規化前）。
        dx / foot_dx / upright / foot_on_floor を参照する。
    effort
        EffortTracker が FRAME_SKIP 物理ステップで積算した負荷。
    """
    upright = step_physics.upright
    foot_on_floor = step_physics.foot_on_floor

    # --- 前進報酬（条件付き）--------------------------------------------------
    # imu_site の dx と foot_site の foot_dx を同条件・同スケールで加点し合計する。
    forward_imu = self._forward_component(
      step_physics.dx, upright=upright, foot_on_floor=foot_on_floor
    )
    forward_foot = self._forward_component(
      step_physics.foot_dx, upright=upright, foot_on_floor=foot_on_floor
    )

    # effort.penalty は常に計算されるが、フラグで学習への反映を切り替え可能
    effort_penalty = effort.penalty if config.APPLY_EFFORT_PENALTY else 0.0

    return RewardBreakdown(
      forward_imu=forward_imu,
      forward_foot=forward_foot,
      effort_penalty=effort_penalty,
      effort_power_cost=effort.power_cost,
    )
