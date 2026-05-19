"""exp_002 のステップ報酬。

設計の狙い
---------
2 関節脚で「前に進む」ことを学習させるが、単純に IMU のワールド +X 変位 (dx) だけを
与えると、体を前に倒して IMU が進むだけでも高報酬になる（前倒れハック）。
そのため次を組み合わせる。

  1. 前進報酬 … 直立かつ足接地など条件を満たすときだけ dx を加点
  2. 筋負荷ペナルティ … |τ·q̇| を正規化して積分（effort.py / env の mj_step ループ）
  3. 終了ペナルティ … env.py で termination.done_reason の penalty を一度だけ加算

1 ステップの合計（env 適用前）::

  total = forward - effort_penalty

係数は config.py。終了判定は termination.py。
"""

from dataclasses import dataclass

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.effort import EffortBreakdown
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.observation import StepPhysics


@dataclass(frozen=True)
class RewardBreakdown:
  """1 ステップ分の報酬の内訳。wandb の episode/forward_reward_sum などの元になる。"""

  forward: float
  effort_penalty: float
  effort_power_cost: float

  @property
  def total(self) -> float:
    return self.forward - self.effort_penalty


class Reward:
  """報酬のみ計算する（早期終了・時間切れの判定は Termination / train）。"""

  def compute(
    self,
    step_physics: StepPhysics,
    *,
    effort: EffortBreakdown,
  ) -> RewardBreakdown:
    """1 環境ステップ分の報酬内訳を返す。

    step_physics
        observation.build が返す当ステップの物理量（正規化前）。
        dx / upright / foot_on_floor を参照する。
  effort
        EffortTracker が FRAME_SKIP 物理ステップで積算した負荷。
    """
    dx = step_physics.dx
    upright = step_physics.upright
    foot_on_floor = step_physics.foot_on_floor

    # dx の外れ値抑制（1 ステップで動きすぎると報酬が跳ねるのを防ぐ）
    dx_clipped = max(-config.MAX_DX_PER_STEP, min(config.MAX_DX_PER_STEP, float(dx)))

    # --- 前進報酬（条件付き）--------------------------------------------------
    # 旧設計: dx * FORWARD_REWARD_SCALE のみ → 前倒れで IMU が進むと高得点になった。
    #
    # 現在の条件（すべて満たすときだけ加点）:
    #   (a) upright >= FORWARD_MIN_UPRIGHT … ある程度立っている
    #   (b) foot_on_floor（設定時）… 足が床についている
    #   (c) max(0, dx_clipped) … 後退分は前進報酬にしない
    #
    # 理由: 「倒れながらの前進」を前進としてカウントしない。
    forward = 0.0
    if upright >= config.FORWARD_MIN_UPRIGHT:
      if not config.FORWARD_REQUIRE_FOOT_CONTACT or foot_on_floor:
        forward = max(0.0, dx_clipped) * config.FORWARD_REWARD_SCALE

    return RewardBreakdown(
      forward=forward,
      effort_penalty=effort.penalty,
      effort_power_cost=effort.power_cost,
    )
