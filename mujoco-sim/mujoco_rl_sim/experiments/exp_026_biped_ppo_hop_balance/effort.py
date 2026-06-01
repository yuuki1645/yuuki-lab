"""全 12 アクチュエータの |τ·q̇| 積分から筋負荷ペナルティ。"""

from dataclasses import dataclass

import mujoco

import config
from lib.actuators import ACTUATOR_NAMES


@dataclass(frozen=True)
class EffortBreakdown:
  power_cost: float
  penalty: float


class EffortTracker:
  def __init__(self, model: mujoco.MjModel):
    self._dt = float(model.opt.timestep)
    self._act_ids: list[int] = []
    self._dof_adr: list[int] = []
    self._tau_max: list[float] = []
    for name in ACTUATOR_NAMES:
      act = model.actuator(name)
      act_id = act.id
      self._act_ids.append(act_id)
      jnt_id = int(model.actuator_trnid[act_id, 0])
      self._dof_adr.append(int(model.jnt_dofadr[jnt_id]))
      fr = model.actuator_forcerange[act_id]
      self._tau_max.append(max(abs(float(fr[0])), abs(float(fr[1]))))
    self._power_cost = 0.0

  def reset_control_step(self) -> None:
    self._power_cost = 0.0

  def record_physics_step(self, data: mujoco.MjData) -> None:
    for act_id, dof_adr, tau_max in zip(
      self._act_ids, self._dof_adr, self._tau_max, strict=True
    ):
      tau = float(data.actuator_force[act_id])
      qvel = float(data.qvel[dof_adr])
      self._power_cost += abs(tau * qvel) / tau_max * self._dt

  def control_step_breakdown(self) -> EffortBreakdown:
    penalty = self._power_cost * config.EFFORT_PENALTY_SCALE
    return EffortBreakdown(power_cost=self._power_cost, penalty=penalty)
