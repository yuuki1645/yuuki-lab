"""歩行制御の編集対象モジュール。

アルゴリズムの具体方針はここに実装する。パラメータは conf/controller.yaml から読む。
action は exp_030 と同じ 12 次元 [-1, 1]（0 = stand 中立）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from runtime.config import ControlParams

# アクチュエータ順（exp_030 lib/actuators.py と一致）
_N_ACTION = 12
_LEFT_HIP_PITCH = 1
_LEFT_KNEE = 2
_LEFT_ANKLE = 3
_RIGHT_HIP_PITCH = 6
_RIGHT_KNEE = 7
_RIGHT_ANKLE = 8
_TORSO_ROLL = 10
_TORSO_PITCH = 11


@dataclass
class ControllerState:
  """制御内部状態（ログ・再現用）。"""

  phase: float = 0.0
  swing_left: bool = True

  def to_dict(self) -> dict[str, float | bool]:
    return {"phase": self.phase, "swing_left": self.swing_left}


class WalkController:
  """v0 開始実装: 位相振動子 + 左右交互の関節オフセット。

  成功を前提としない。run の軌道ログと incident 記録から AI が改善する。
  """

  def __init__(self, params: ControlParams | None = None):
    self.params = params or ControlParams()
    self.state = ControllerState()

  def reset(self) -> None:
    self.state = ControllerState(
      phase=float(self.params.phase_offset),
      swing_left=True,
    )

  def compute_action(
    self,
    *,
    step: int,
    obs: np.ndarray,
    env: Any,
    control_dt: float,
  ) -> tuple[tuple[float, ...], dict[str, float | bool]]:
    """1 制御ステップ分の action と内部変数を返す。"""
    p = self.params
    st = self.state

    st.phase = (st.phase + control_dt / max(p.cycle_period_s, 1e-6)) % 1.0
    if st.phase < control_dt / max(p.cycle_period_s, 1e-6):
      st.swing_left = not st.swing_left

    action = [0.0] * _N_ACTION
    wave = math.sin(2.0 * math.pi * st.phase)

    if st.swing_left:
      action[_LEFT_HIP_PITCH] = p.swing_hip_pitch * wave
      action[_LEFT_KNEE] = p.swing_knee * max(wave, 0.0)
      action[_LEFT_ANKLE] = p.swing_ankle_pitch * wave
      action[_RIGHT_HIP_PITCH] = p.stance_hip_pitch
      action[_RIGHT_KNEE] = p.stance_knee
    else:
      action[_RIGHT_HIP_PITCH] = p.swing_hip_pitch * wave
      action[_RIGHT_KNEE] = p.swing_knee * max(wave, 0.0)
      action[_RIGHT_ANKLE] = p.swing_ankle_pitch * wave
      action[_LEFT_HIP_PITCH] = p.stance_hip_pitch
      action[_LEFT_KNEE] = p.stance_knee

    # 観測から直立成分を弱く補正（idx 4-6 が imu_zaxis、7 が imu_z norm）
    if obs.shape[0] >= 8:
      imu_z_norm = float(obs[7])
      tilt_x = float(obs[4]) if obs.shape[0] > 4 else 0.0
      action[_TORSO_PITCH] = p.torso_balance_gain * (1.0 - imu_z_norm)
      action[_TORSO_ROLL] = -p.torso_roll_damp * tilt_x

    clipped = tuple(float(np.clip(a, -1.0, 1.0)) for a in action)
    debug = {
      **st.to_dict(),
      "wave": wave,
      "step": float(step),
    }
    return clipped, debug
