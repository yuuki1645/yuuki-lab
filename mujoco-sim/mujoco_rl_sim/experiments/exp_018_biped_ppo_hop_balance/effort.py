"""関節トルク・角速度から筋負荷（エネルギー消耗）の代理ペナルティを計算する。

1 物理ステップあたりの寄与（正規化済み）::

  |τ·q̇| * dt / τ_max

τ は data.actuator_force [N·m]、q̇ は対応ヒンジの data.qvel [rad/s]。
τ_max は XML の actuator forcerange から取った片側最大（非対称関節に対応）。
"""

from dataclasses import dataclass

import mujoco

from . import config


@dataclass(frozen=True)
class EffortBreakdown:
  """1 制御ステップ（FRAME_SKIP 物理ステップ）分の負荷内訳。"""

  power_cost: float  # Σ |τ·q̇|·dt/τ_max（無次元・時間積分）
  penalty: float  # reward から引く正值


class EffortTracker:
  """mj_step ごとに負荷を積算し、制御ステップ末にペナルティを返す。"""

  def __init__(self, model: mujoco.MjModel):
    self._dt = float(model.opt.timestep)
    # 膝・足首サーボと、それが駆動する関節 DOF を起動時に解決
    actuators = (
      model.actuator("knee_servo"),
      model.actuator("ankle_servo"),
    )
    self._act_ids = tuple(a.id for a in actuators)
    self._dof_adr = tuple(
      int(model.jnt_dofadr[int(model.actuator_trnid[act_id, 0])])
      for act_id in self._act_ids
    )
    self._tau_max = tuple(
      max(abs(float(model.actuator_forcerange[act_id, 0])), abs(float(model.actuator_forcerange[act_id, 1])))
      for act_id in self._act_ids
    )
    self._power_cost = 0.0

  def reset_control_step(self) -> None:
    self._power_cost = 0.0

  def record_physics_step(self, data: mujoco.MjData) -> None:
    """mj_step 直後に呼ぶ。"""
    for act_id, dof_adr, tau_max in zip(self._act_ids, self._dof_adr, self._tau_max, strict=True):
      tau = float(data.actuator_force[act_id])
      qvel = float(data.qvel[dof_adr])
      self._power_cost += abs(tau * qvel) / tau_max * self._dt

  def control_step_breakdown(self) -> EffortBreakdown:
    """制御ステップ末に積算結果を返す。報酬への反映は reward.py / APPLY_EFFORT_PENALTY。"""
    penalty = self._power_cost * config.EFFORT_PENALTY_SCALE
    return EffortBreakdown(power_cost=self._power_cost, penalty=penalty)
