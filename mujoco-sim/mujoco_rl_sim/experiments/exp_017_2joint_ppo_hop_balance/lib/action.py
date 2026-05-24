import mujoco

from .ctrl import action_to_ctrl, clip_policy_action


class ActionBinding:
  """ポリシー出力 [-1, 1]² を knee / ankle の ctrl に書き込む。

  actuator ID と ctrlrange は model 構築時に一度だけ解決する。
  """

  def __init__(self, model: mujoco.MjModel):
    knee = model.actuator("knee_servo")
    ankle = model.actuator("ankle_servo")
    self._knee_act_id = knee.id
    self._ankle_act_id = ankle.id
    self._knee_ctrl_range = model.actuator_ctrlrange[knee.id].copy()
    self._ankle_ctrl_range = model.actuator_ctrlrange[ankle.id].copy()

  def apply(self, data: mujoco.MjData, action) -> tuple[float, float]:
    """action をクリップして data.ctrl に反映し、クリップ後の (knee, ankle) を返す。"""
    knee_a = clip_policy_action(action[0])
    ankle_a = clip_policy_action(action[1])
    data.ctrl[self._knee_act_id] = action_to_ctrl(knee_a, self._knee_ctrl_range)
    data.ctrl[self._ankle_act_id] = action_to_ctrl(ankle_a, self._ankle_ctrl_range)
    return knee_a, ankle_a
