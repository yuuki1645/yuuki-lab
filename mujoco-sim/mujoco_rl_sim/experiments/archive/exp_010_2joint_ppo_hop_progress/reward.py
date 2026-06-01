"""exp_009: 片脚ホッパ向けステップ報酬（exp_008 + 前傾ゲート・長飛翔ペナルティ）。

検証の読み方
------------
1. 下の「記号・座標」を確認（符号を間違えると前傾/後傾が逆になる）
2. `compute()` の項の順に、各 `_xxx` のゲート表と式を照合
3. 係数はすべて `config.py`（ここでは名前だけ参照）

1 制御ステップ（50 Hz）あたりの合計（env が終了ペナルティを足す前）::

  total = forward_imu + forward_foot
          + upright_bonus + push_off_bonus + landing_bonus
          - backward_lean_penalty - forward_lean_penalty - height_penalty
          - flight_duration_penalty - effort_penalty

  ※ 膝屈曲ボーナスは exp_006 から削除（歩行向けだった）
  ※ shank 接触ペナルティは env.py（本ファイル外）

記号・座標（StepPhysics / HopStepContext）
-----------------------------------------
| 変数 | 意味 |
|------|------|
| dx | 直前 step からの imu_site ワールド X 変位 [m]。+ = 前進 |
| foot_dx | 直前 step からの foot_site ワールド X 変位 [m] |
| upright | imu_zaxis_z（IMU 上向きベクトルの z 成分）。1 に近いほど直立 |
| imu_zaxis_x | IMU 上向きベクトルの x 成分。**+ = 前傾、− = 後傾** |
| imu_z | imu_site のワールド Z [m] |
| foot_on_floor | 足裏 geom と床の接触あり |
| knee_angle | 膝 qpos [rad]。+Y ヒンジで **+ = 後方屈曲** |
| knee_vel | 膝 qvel [rad/s]。**負 = 角が減少 = 伸展** |
| toe_z, heel_z | 足底板端 site のワールド Z [m]（低い = 床に近い） |

HopStepContext（episode_state が毎 step 更新）:
| 変数 | 意味 |
|------|------|
| landed | 直前 step は非接地 & 今 step は接地 → 着地エッジで True（1 step だけ） |
| flight_steps | 連続非接地 step 数（接地で 0 にリセット） |
| imu_dz | 直前 step からの imu_z 変化 [m]。+ = 上昇 |

ホップ周期との対応（意図）
------------------------
  立脚(接地) ──押し出し──> 飛翔(非接地) ──着地──> 立脚 ...
       │                      │                    │
  push_off_bonus          forward_imu            landing_bonus
  forward_foot            upright_bonus          (landed=True)
  height(緩い)            forward_lean_penalty
                          height(墜落寄り)
"""

from dataclasses import dataclass

import config
from effort import EffortBreakdown
from episode_state import HopStepContext
from observation import StepPhysics


@dataclass(frozen=True)
class RewardBreakdown:
  """1 step の報酬内訳。wandb / step_info のキー名と対応。"""

  forward_imu: float
  forward_foot: float
  upright_bonus: float
  push_off_bonus: float
  landing_bonus: float
  backward_lean_penalty: float
  forward_lean_penalty: float
  height_penalty: float
  flight_duration_penalty: float
  progress_bonus: float
  knee_hyperflex_penalty: float
  effort_penalty: float
  effort_power_cost: float  # ログ用（total には effort_penalty のみ反映）

  @property
  def forward(self) -> float:
    return self.forward_imu + self.forward_foot

  @property
  def shaping(self) -> float:
    """前進以外の shaping 合計（wandb episode/shaping_sum）。"""
    return (
      self.upright_bonus
      + self.push_off_bonus
      + self.landing_bonus
      + self.progress_bonus
      - self.backward_lean_penalty
      - self.forward_lean_penalty
      - self.height_penalty
      - self.flight_duration_penalty
      - self.knee_hyperflex_penalty
    )

  @property
  def total(self) -> float:
    return self.forward + self.shaping - self.effort_penalty


class Reward:
  """片脚ホッパ向け報酬。位相（接地/非接地）でゲートする項が多い。"""

  @staticmethod
  def _forward_imu_lean_multiplier(
    imu_zaxis_x: float, *, foot_on_floor: bool
  ) -> float:
    """飛翔中の前傾が強いほど IMU 前進報酬を減衰（exp_009）。"""
    if not config.FORWARD_IMU_LEAN_GATE or foot_on_floor:
      return 1.0
    excess = max(
      0.0, float(imu_zaxis_x) - config.FORWARD_IMU_LEAN_GATE_THRESH
    )
    mult = 1.0 - config.FORWARD_IMU_LEAN_GATE_SCALE * excess
    return max(config.FORWARD_IMU_LEAN_GATE_MIN_MULT, mult)

  @staticmethod
  def _flight_duration_penalty(*, foot_on_floor: bool, flight_steps: int) -> float:
    """着地しない長い飛翔へのステップペナルティ（exp_009）。"""
    if foot_on_floor:
      return 0.0
    over = flight_steps - config.FLIGHT_DURATION_PENALTY_AFTER_STEPS
    if over <= 0:
      return 0.0
    return over * config.FLIGHT_DURATION_PENALTY_SCALE

  @staticmethod
  def _progress_bonus(progress_m: float) -> float:
    return float(progress_m) * config.PROGRESS_REWARD_SCALE

  @staticmethod
  def _knee_hyperflex_penalty(
    knee_angle: float, *, foot_on_floor: bool
  ) -> float:
    if config.KNEE_HYPERFLEX_FLIGHT_ONLY and foot_on_floor:
      return 0.0
    excess = max(0.0, float(knee_angle) - config.KNEE_HYPERFLEX_MAX_RAD)
    return excess * config.KNEE_HYPERFLEX_PENALTY_SCALE

  @staticmethod
  def _forward_component(
    dx: float,
    *,
    upright: float,
    foot_on_floor: bool,
    allow_without_contact: bool,
    scale: float = 1.0,
  ) -> float:
    """前進報酬の共通コア（IMU 用 / foot 用で allow_without_contact だけ変える）。

    式（すべて満たすとき）::

      reward = max(0, clip(dx, ±MAX_DX_PER_STEP)) * FORWARD_REWARD_SCALE

    ゲート（1 つでも満たさないと 0）:
      G1. upright >= FORWARD_MIN_UPRIGHT   … 大きく傾いた「前進」は除外
      G2. FORWARD_REQUIRE_FOOT_CONTACT 時は foot_on_floor 必須
          （exp_008 では False → 飛翔中の IMU dx は G2 を通過）
      G3. allow_without_contact が False のとき foot_on_floor 必須
          → foot_dx 用。立脚中だけ足元の前進を評価

  検証メモ:
      - 後退（dx<0）は max(0,·) で 0。前進のみ加点
      - IMU: allow_without_contact=True  → ホップの飛翔前進の主報酬
      - foot: allow_without_contact=接地時のみ → 滑り/空中の foot 移動は無報酬
    """
    dx_clipped = max(-config.MAX_DX_PER_STEP, min(config.MAX_DX_PER_STEP, float(dx)))
    if upright < config.FORWARD_MIN_UPRIGHT:
      return 0.0
    if config.FORWARD_REQUIRE_FOOT_CONTACT and not foot_on_floor:
      return 0.0
    if not allow_without_contact and not foot_on_floor:
      return 0.0
    return max(0.0, dx_clipped) * config.FORWARD_REWARD_SCALE * max(0.0, float(scale))

  @staticmethod
  def _upright_bonus(
    upright: float, *, dx: float, foot_on_floor: bool
  ) -> float:
    """飛翔中の「まっすぐ前に進んでいる」ことへの小ボーナス（常時直立は廃止）。

    式::

      bonus = max(0, upright - UPRIGHT_BONUS_THRESH) * UPRIGHT_BONUS_SCALE

    ゲート:
      G1. UPRIGHT_BONUS_REQUIRE_FLIGHT → 接地中は 0（立脚は push_off / foot_dx へ）
      G2. dx >= UPRIGHT_BONUS_MIN_DX   … 止まったまま直立だけでは得点しない
           （exp_008 では MIN_DX=0 なので実質オフ）

  exp_006 との違い: 常時 upright ボーナス → 飛翔限定。
    """
    if config.UPRIGHT_BONUS_REQUIRE_FLIGHT and foot_on_floor:
      return 0.0
    if dx < config.UPRIGHT_BONUS_MIN_DX:
      return 0.0
    return (
      max(0.0, float(upright) - config.UPRIGHT_BONUS_THRESH)
      * config.UPRIGHT_BONUS_SCALE
    )

  @staticmethod
  def _backward_lean_penalty(imu_zaxis_x: float) -> float:
    """後傾ペナルティ（exp_001 系を維持）。

    式::

      excess = max(0, -imu_zaxis_x - LEAN_BACKWARD_THRESH)
      penalty = excess * LEAN_BACKWARD_PENALTY_SCALE

    解釈: imu_zaxis_x が負（体軸が −X = 後ろに倒れる）ほど増える。
    接地/非接地の区別なし（常時）。
    """
    excess = max(0.0, -float(imu_zaxis_x) - config.LEAN_BACKWARD_THRESH)
    return excess * config.LEAN_BACKWARD_PENALTY_SCALE

  @staticmethod
  def _forward_lean_penalty(
    imu_zaxis_x: float, *, foot_on_floor: bool, flight_steps: int
  ) -> float:
    """前傾ダイブ抑制（exp_006 に無かった項）。

    式::

      excess = max(0, imu_zaxis_x - LEAN_FORWARD_THRESH)
      penalty = excess * LEAN_FORWARD_PENALTY_SCALE

    ゲート（空中ダイブだけを狙う）:
      G1. foot_on_floor → 0（立脚の前傾は別途 push_off / 終了条件で扱う）
      G2. flight_steps < LEAN_FORWARD_MIN_FLIGHT_STEPS → 0
           … 離地直後の一瞬の前傾は許容（デフォルト 3 step = 60 ms）

    検証メモ: 長い非接地 + imu_zaxis_x>0.18 あたりから増加。
    """
    if foot_on_floor:
      return 0.0
    if flight_steps < config.LEAN_FORWARD_MIN_FLIGHT_STEPS:
      return 0.0
    excess = max(0.0, float(imu_zaxis_x) - config.LEAN_FORWARD_THRESH)
    return excess * config.LEAN_FORWARD_PENALTY_SCALE

  @staticmethod
  def _height_penalty(imu_z: float, *, foot_on_floor: bool) -> float:
    """低姿勢ペナルティ（立脚と飛翔で挙動を変える）。

    【立脚・接地中】HEIGHT_PENALTY_SKIP_WHEN_STANCE=True のとき::

      target = TARGET_IMU_Z_STANCE  （例 0.48 m、通常より低く許容）
      penalty = max(0, target - imu_z) * IMU_HEIGHT_PENALTY_SCALE
      … 押し込み（しゃがみ）を歩行時より嫌わない

    【飛翔・非接地】
      (A) imu_z < HEIGHT_PENALTY_FLIGHT_CRASH_Z のとき
          penalty = max(0, TARGET_IMU_Z - imu_z) * SCALE * 1.5  … 墜落寄りを強調
      (B) それ以外
          penalty = max(0, TARGET_IMU_Z - imu_z) * SCALE

    検証メモ: 飛翔中に imu_z が 0.55 未満だと (B) でも徐々に減点。
    """
    if config.HEIGHT_PENALTY_SKIP_WHEN_STANCE and foot_on_floor:
      target = config.TARGET_IMU_Z_STANCE
      deficit = max(0.0, target - float(imu_z))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE
    if float(imu_z) < config.HEIGHT_PENALTY_FLIGHT_CRASH_Z:
      deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
      return deficit * config.IMU_HEIGHT_PENALTY_SCALE * 1.5
    deficit = max(0.0, config.TARGET_IMU_Z - float(imu_z))
    return deficit * config.IMU_HEIGHT_PENALTY_SCALE

  @staticmethod
  def _push_off_bonus(
    step_physics: StepPhysics,
    *,
    hop: HopStepContext,
  ) -> float:
    """立脚フェーズの押し出しボーナス（定数、最大 PUSH_OFF_BONUS_SCALE）。

    ゲート（すべて必須）:
      G1. foot_on_floor
      G2. foot_dx >= PUSH_OFF_MIN_FOOT_DX   … 足元が前に動いている
      G3. 次のいずれか
            (a) knee_vel < -PUSH_OFF_MIN_KNEE_EXT_VEL  … 膝が伸展中
            (b) hop.imu_dz >= PUSH_OFF_MIN_IMU_DZ      … 胴体が上昇中

    検証メモ（膝の符号）:
      +Y ヒンジ・屈曲が knee_angle>0 → 伸展は knee_vel<0。
      hop.imu_dz は episode_state が prev_imu_z との差分で計算。

    exp_006 の knee_flex 常時ボーナスとは独立（曲げたままでも G3 を満たせば得点）。
    """
    if not step_physics.foot_on_floor:
      return 0.0
    if step_physics.foot_dx < config.PUSH_OFF_MIN_FOOT_DX:
      return 0.0
    extending = step_physics.knee_vel < -config.PUSH_OFF_MIN_KNEE_EXT_VEL
    rising = hop.imu_dz >= config.PUSH_OFF_MIN_IMU_DZ
    if not (extending or rising):
      return 0.0
    return config.PUSH_OFF_BONUS_SCALE

  @staticmethod
  def _landing_bonus(step_physics: StepPhysics, *, hop: HopStepContext) -> float:
    """着地エッジの 1 回ボーナス（定数 LANDING_BONUS_SCALE）。

    ゲート（すべて必須）:
      G1. hop.landed … 非接地→接地に変わった step のみ True
      G2. toe_z <= LANDING_MAX_TOE_Z  かつ  heel_z <= LANDING_MAX_HEEL_Z
           … 足底板端が床に近い（足首だけ接地などを除外したい意図）
      G3. imu_zaxis_x <= LANDING_MAX_FORWARD_LEAN
           … 強い前傾での着地はボーナスなし

    検証メモ: landed は advance_hop_context() 内で
      landed = foot_on_floor and not prev_foot_on_floor
    """
    if not hop.landed:
      return 0.0
    if step_physics.toe_z > config.LANDING_MAX_TOE_Z:
      return 0.0
    if step_physics.heel_z > config.LANDING_MAX_HEEL_Z:
      return 0.0
    if step_physics.imu_zaxis_x > config.LANDING_MAX_FORWARD_LEAN:
      return 0.0
    return config.LANDING_BONUS_SCALE

  def compute(
    self,
    step_physics: StepPhysics,
    *,
    hop: HopStepContext,
    effort: EffortBreakdown,
    progress_m: float = 0.0,
  ) -> RewardBreakdown:
    """1 環境 step の報酬内訳を計算する。

    呼び出し元（env.py）の流れ:
      1. observation.build → step_physics
      2. episode_state.advance_hop_context → hop
      3. 本メソッド
      4. reward = breakdown.total + termination.penalty + shank_penalty

    項の計算順（検証時はこの順で追うとよい）:
      ① forward_imu  … dx, 飛翔含む
      ② forward_foot … foot_dx, 接地時のみ
      ③ upright_bonus
      ④ push_off_bonus
      ⑤ landing_bonus
      ⑥ backward_lean_penalty
      ⑦ forward_lean_penalty  … flight_steps 要
      ⑧ height_penalty
      ⑨ effort_penalty        … APPLY_EFFORT_PENALTY 時のみ
    """
    upright = step_physics.upright
    foot_on_floor = step_physics.foot_on_floor
    # True のとき foot_dx は接地中だけ前進報酬対象（config.FORWARD_FOOT_ONLY_WHEN_CONTACT）
    foot_forward_allowed = not config.FORWARD_FOOT_ONLY_WHEN_CONTACT or foot_on_floor

    imu_forward_scale = self._forward_imu_lean_multiplier(
      step_physics.imu_zaxis_x, foot_on_floor=foot_on_floor
    )
    forward_imu = self._forward_component(
      step_physics.dx,
      upright=upright,
      foot_on_floor=foot_on_floor,
      allow_without_contact=True,
      scale=imu_forward_scale,
    )
    forward_foot = self._forward_component(
      step_physics.foot_dx,
      upright=upright,
      foot_on_floor=foot_on_floor,
      allow_without_contact=foot_forward_allowed,
    )

    effort_penalty = effort.penalty if config.APPLY_EFFORT_PENALTY else 0.0

    return RewardBreakdown(
      forward_imu=forward_imu,
      forward_foot=forward_foot,
      upright_bonus=self._upright_bonus(
        upright, dx=step_physics.dx, foot_on_floor=foot_on_floor
      ),
      push_off_bonus=self._push_off_bonus(step_physics, hop=hop),
      landing_bonus=self._landing_bonus(step_physics, hop=hop),
      backward_lean_penalty=self._backward_lean_penalty(step_physics.imu_zaxis_x),
      forward_lean_penalty=self._forward_lean_penalty(
        step_physics.imu_zaxis_x,
        foot_on_floor=foot_on_floor,
        flight_steps=hop.flight_steps,
      ),
      height_penalty=self._height_penalty(
        step_physics.imu_z, foot_on_floor=foot_on_floor
      ),
      flight_duration_penalty=self._flight_duration_penalty(
        foot_on_floor=foot_on_floor, flight_steps=hop.flight_steps
      ),
      progress_bonus=self._progress_bonus(progress_m),
      knee_hyperflex_penalty=self._knee_hyperflex_penalty(
        step_physics.knee_angle, foot_on_floor=foot_on_floor
      ),
      effort_penalty=effort_penalty,
      effort_power_cost=effort.power_cost,
    )
