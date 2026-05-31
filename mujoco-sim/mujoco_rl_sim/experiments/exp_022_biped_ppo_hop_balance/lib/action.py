import mujoco
import numpy as np

from lib.actuators import ACTUATOR_NAMES
from lib.ctrl import action_to_ctrl, clip_policy_action


class ActionBinding:
  """ポリシー出力 [-1, 1]^N を全 position アクチュエータの ctrl に書き込む。

  action=0 は keyframe ``stand`` の関節角（中立姿勢）。ctrlrange の中点ではない。
  """

  def __init__(self, model: mujoco.MjModel):
    self._act_ids: list[int] = []
    self._ctrl_ranges: list[tuple[float, float]] = []
    self._neutral_ctrl: list[float] = []

    neutral_q: dict[str, float] = {}
    key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
    if key_id >= 0:
      scratch = mujoco.MjData(model)
      mujoco.mj_resetDataKeyframe(model, scratch, key_id)
      for name in ACTUATOR_NAMES:
        jn = name.replace("_motor", "")
        neutral_q[jn] = float(scratch.joint(jn).qpos[0])

    for name in ACTUATOR_NAMES:
      act = model.actuator(name)
      self._act_ids.append(act.id)
      lo, hi = model.actuator_ctrlrange[act.id]
      self._ctrl_ranges.append((float(lo), float(hi)))
      jn = name.replace("_motor", "")
      q_nom = neutral_q.get(jn, 0.5 * (float(lo) + float(hi)))
      self._neutral_ctrl.append(float(np.clip(q_nom, float(lo), float(hi))))

  def apply(self, data: mujoco.MjData, action) -> tuple[float, ...]:
    clipped: list[float] = []
    for act_id, ctrl_range, neutral, raw in zip(
      self._act_ids, self._ctrl_ranges, self._neutral_ctrl, action, strict=True
    ):
      a = clip_policy_action(raw)
      data.ctrl[act_id] = action_to_ctrl(
        a, ctrl_range, neutral_ctrl=neutral
      )
      clipped.append(a)
    return tuple(clipped)
