import mujoco

from .actuators import ACTUATOR_NAMES
from .ctrl import action_to_ctrl, clip_policy_action


class ActionBinding:
  """ポリシー出力 [-1, 1]^N を全 position アクチュエータの ctrl に書き込む。"""

  def __init__(self, model: mujoco.MjModel):
    self._act_ids: list[int] = []
    self._ctrl_ranges: list[tuple[float, float]] = []
    for name in ACTUATOR_NAMES:
      act = model.actuator(name)
      self._act_ids.append(act.id)
      lo, hi = model.actuator_ctrlrange[act.id]
      self._ctrl_ranges.append((float(lo), float(hi)))

  def apply(self, data: mujoco.MjData, action) -> tuple[float, ...]:
    clipped: list[float] = []
    for act_id, (lo, hi), raw in zip(
      self._act_ids, self._ctrl_ranges, action, strict=True
    ):
      a = clip_policy_action(raw)
      data.ctrl[act_id] = action_to_ctrl(a, (lo, hi))
      clipped.append(a)
    return tuple(clipped)
