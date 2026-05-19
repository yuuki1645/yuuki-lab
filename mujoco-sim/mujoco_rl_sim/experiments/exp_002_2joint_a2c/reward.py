"""exp_002 のステップ報酬。

設計の狙い
---------
2 関節脚で「前に進む」ことを学習させるが、単純に IMU のワールド +X 変位 (dx) だけを
与えると、体を前に倒して IMU が進むだけでも高報酬になる（前倒れハック）。
そのため次を組み合わせる。

  1. 前進報酬 … 直立かつ足接地など条件を満たすときだけ dx を加点
  2. 姿勢ボーナス … しっかり立っている時間に小さな加点
  3. 膝の形 … 人間らしい屈曲レンジに小ボーナス（XML で qpos >= 0 のみ可動）
  4. 後傾・低姿勢ペナルティ … 後ろに倒れる／しゃがみ込みを早めに減点
  5. 終了ペナルティ … env.py で termination.done_reason の penalty を一度だけ加算

1 ステップの合計（env 適用前）::

  total = forward + upright + knee_flex_bonus - backward_lean_penalty - height_penalty

係数は config.py。終了判定は termination.py。
"""

from dataclasses import dataclass

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.observation import StepPhysics


@dataclass(frozen=True)
class RewardBreakdown:
  """1 ステップ分の報酬の内訳。wandb の episode/forward_reward_sum などの元になる。"""

  forward: float
  upright: float
  knee_flex_bonus: float
  backward_lean_penalty: float
  height_penalty: float

  @property
  def total(self) -> float:
    return (
      self.forward
      + self.upright
      + self.knee_flex_bonus
      - self.backward_lean_penalty
      - self.height_penalty
    )


class Reward:
  """報酬のみ計算する（早期終了・時間切れの判定は Termination / train）。"""

  def compute(self, step_physics: StepPhysics) -> RewardBreakdown:
    """1 環境ステップ分の報酬内訳を返す。

    step_physics
        observation.build が返す当ステップの物理量（正規化前）。
        dx / upright / knee_angle / foot_on_floor / imu_z / imu_zaxis_x を参照する。
    """
    dx = step_physics.dx
    upright = step_physics.upright
    knee_angle = step_physics.knee_angle
    foot_on_floor = step_physics.foot_on_floor
    imu_z = step_physics.imu_z
    imu_zaxis_x = step_physics.imu_zaxis_x
    # --- 膝: 人間的な屈曲レンジの小ボーナス -----------------------------------
    # 適度な後方屈曲のときだけ定数ボーナス（dx とは独立）。
    # 理由: 完全に伸ばしたまま引きずる／棒立ちを避け、歩の形のヒントにする。
    knee_flex_bonus = 0.0
    if config.KNEE_HUMAN_FLEX_MIN_RAD <= knee_angle <= config.KNEE_HUMAN_FLEX_MAX_RAD:
      knee_flex_bonus = config.KNEE_HUMAN_FLEX_BONUS_SCALE

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

    # --- 直立ボーナス ----------------------------------------------------------
    # upright が UPRIGHT_BONUS_THRESH より高い分だけ線形に加点。
    # 前進ゲート（0.72）より緩い閾値（0.65）で、立ち方の改善を促す。
    # 理由: 前進だけだと姿勢が犠牲になりやすいので、立っていること自体にも報酬。
    upright_bonus = (
      max(0.0, upright - config.UPRIGHT_BONUS_THRESH) * config.UPRIGHT_BONUS_SCALE
    )

    # --- 後傾ペナルティ --------------------------------------------------------
    # imu_zaxis_x が負 = 体が後ろ（−X）に傾いている。LEAN_BACKWARD_THRESH を超えた分を減点。
    # 理由: mean_upright だけでは後傾と区別しにくいため、別軸でペナルティ。
    backward_lean_excess = max(0.0, -float(imu_zaxis_x) - config.LEAN_BACKWARD_THRESH)
    backward_lean_penalty = backward_lean_excess * config.LEAN_BACKWARD_PENALTY_SCALE

    # --- 低姿勢ペナルティ ------------------------------------------------------
    # imu_z が TARGET_IMU_Z より低いほど減点（しゃがみ／倒れ込み）。
    # 理由: 高さが落ちる前に「低くなりすぎ」を抑える。
    height_deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
    height_penalty = height_deficit * config.IMU_HEIGHT_PENALTY_SCALE

    return RewardBreakdown(
      forward=forward,
      upright=upright_bonus,
      knee_flex_bonus=knee_flex_bonus,
      backward_lean_penalty=backward_lean_penalty,
      height_penalty=height_penalty,
    )
