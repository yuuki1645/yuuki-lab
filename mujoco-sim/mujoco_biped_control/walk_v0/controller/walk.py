"""歩行制御の編集対象モジュール。

周期スケジューラで左右交互の歩容を生成する（exp_030 上で grid search により調整済み）。
パラメータは conf/controller.yaml。action は 12 次元 [-1, 1]（0 = stand 中立）。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

import numpy as np

from runtime.config import ControlParams

# アクチュエータ順（exp_030 lib/actuators.py と一致）
_N_ACTION = 12
_L_HIP_R, _L_HIP_P, _L_KNEE, _L_ANK, _L_ANK_R = 0, 1, 2, 3, 4
_R_HIP_R, _R_HIP_P, _R_KNEE, _R_ANK, _R_ANK_R = 5, 6, 7, 8, 9
_TORSO_ROLL, _TORSO_PITCH = 10, 11

# 観測 idx（biped_walk_v1）
_OBS_IMU_Z_NORM = 7
_OBS_IMU_ZAXIS_X = 4


class GaitPhase(enum.Enum):
  """ログ用の離散位相（周期内位置から決定）。"""

  DOUBLE_SUPPORT = "double_support"
  SWING_RIGHT = "swing_right"  # 左足支持・右足遊脚
  SWING_LEFT = "swing_left"  # 右足支持・左足遊脚


@dataclass
class ControllerState:
  phase: GaitPhase = GaitPhase.DOUBLE_SUPPORT
  subphase: float = 0.0  # 位相内進行 [0, 1]
  phase_step: int = 0
  step_count: int = 0  # 完了した遊脚半周期の数
  last_swing: str = ""
  cycle_index: int = 0

  def to_dict(self) -> dict[str, float | bool | str]:
    return {
      "phase": self.phase.value,
      "subphase": self.subphase,
      "phase_step": float(self.phase_step),
      "step_count": float(self.step_count),
      "last_swing": self.last_swing,
      "cycle_index": float(self.cycle_index),
    }


def _lerp(a: float, b: float, t: float) -> float:
  t = float(np.clip(t, 0.0, 1.0))
  return a + (b - a) * t


def _tri_wave01(t: float) -> float:
  """0→1→0 の三角波（遊脚膝の持ち上げ用）。"""
  t = float(np.clip(t, 0.0, 1.0))
  return 1.0 - abs(2.0 * t - 1.0)


class WalkController:
  """周期ベース左右交互歩行制御。"""

  def __init__(self, params: ControlParams | None = None):
    self.params = params or ControlParams()
    self.state = ControllerState()
    self._prev_action: list[float] = [0.0] * _N_ACTION

  def reset(self) -> None:
    self.state = ControllerState()
    self._prev_action = [0.0] * _N_ACTION

  def _cycle_layout(self, control_dt: float) -> tuple[int, int, int]:
    """(period_steps, ds_steps, swing_half_steps) を返す。"""
    p = self.params
    period = max(int(p.cycle_period_s / control_dt), 3)
    ds_steps = max(int(p.double_support_s / control_dt), 1)
    remain = max(period - ds_steps, 2)
    swing_half = max(remain // 2, 1)
    return period, ds_steps, swing_half

  def _update_state_from_step(self, step: int, control_dt: float) -> None:
    """現在 step から FSM 状態（ログ用）を更新する。"""
    period, ds_steps, swing_half = self._cycle_layout(control_dt)
    cycle_step = step % period
    st = self.state

    st.cycle_index = step // period
    completed_swings = st.cycle_index * 2
    if cycle_step >= ds_steps + swing_half:
      st.phase = GaitPhase.SWING_LEFT
      st.phase_step = cycle_step - ds_steps - swing_half
      st.subphase = st.phase_step / max(swing_half - 1, 1)
      completed_swings += 1
      st.last_swing = "left"
    elif cycle_step >= ds_steps:
      st.phase = GaitPhase.SWING_RIGHT
      st.phase_step = cycle_step - ds_steps
      st.subphase = st.phase_step / max(swing_half - 1, 1)
      st.last_swing = "right"
    else:
      st.phase = GaitPhase.DOUBLE_SUPPORT
      st.phase_step = cycle_step
      st.subphase = cycle_step / max(ds_steps - 1, 1)

    _ = completed_swings  # step_count は位相境界で更新
    local = max(0, cycle_step - ds_steps)
    if local >= 2 * swing_half:
      st.step_count = st.cycle_index * 2 + 2
    elif local >= swing_half:
      st.step_count = st.cycle_index * 2 + 1
    else:
      st.step_count = st.cycle_index * 2

  def _double_support_action(self, p: ControlParams, *, weight: float) -> list[float]:
    """両足支持：前傾ベース姿勢へ滑らかに遷移。"""
    w = float(np.clip(weight, 0.0, 1.0))
    action = self._prev_action[:]
    targets = {
      _L_HIP_P: p.base_hip_pitch,
      _L_KNEE: p.base_knee,
      _L_ANK: p.base_ankle_pitch,
      _R_HIP_P: p.base_hip_pitch,
      _R_KNEE: p.base_knee,
      _R_ANK: p.base_ankle_pitch,
      _TORSO_PITCH: p.base_torso_pitch,
    }
    for idx, val in targets.items():
      action[idx] = _lerp(action[idx], val, w)
    return action

  def _swing_right_action(
    self, p: ControlParams, t: float
  ) -> list[float]:
    """左支持・右遊脚。"""
    tri = _tri_wave01(t)
    return [
      p.stance_roll,  # L hip roll: 荷重を左へ
      p.base_hip_pitch + p.stance_hip_delta,
      p.base_knee + p.stance_knee_delta,
      p.base_ankle_pitch + p.stance_ankle_delta,
      0.0,
      p.swing_roll_scale * p.stance_roll,  # R hip roll
      p.base_hip_pitch + p.swing_hip_delta,
      p.base_knee + p.swing_knee_amp * tri,
      p.swing_ankle_lift,
      0.0,
      0.0,
      p.base_torso_pitch,
    ]

  def _swing_left_action(self, p: ControlParams, t: float) -> list[float]:
    """右支持・左遊脚。"""
    tri = _tri_wave01(t)
    return [
      -p.swing_roll_scale * p.stance_roll,
      p.base_hip_pitch + p.swing_hip_delta,
      p.base_knee + p.swing_knee_amp * tri,
      p.swing_ankle_lift,
      0.0,
      -p.stance_roll,
      p.base_hip_pitch + p.stance_hip_delta,
      p.base_knee + p.stance_knee_delta,
      p.base_ankle_pitch + p.stance_ankle_delta,
      0.0,
      0.0,
      p.base_torso_pitch,
    ]

  def _apply_balance(self, action: list[float], obs: np.ndarray, p: ControlParams) -> None:
    """IMU から胴体を微補正（周期バイアスに上乗せ）。"""
    if obs.shape[0] <= _OBS_IMU_Z_NORM:
      return
    imu_z_norm = float(obs[_OBS_IMU_Z_NORM])
    tilt_x = float(obs[_OBS_IMU_ZAXIS_X])
    pitch_err = 1.0 - imu_z_norm
    action[_TORSO_PITCH] = float(
      np.clip(
        action[_TORSO_PITCH] + p.torso_balance_gain * pitch_err,
        -0.35,
        0.35,
      )
    )
    action[_TORSO_ROLL] = float(
      np.clip(-p.torso_roll_damp * tilt_x, -0.25, 0.25)
    )

  def compute_action(
    self,
    *,
    step: int,
    obs: np.ndarray,
    env: Any,
    control_dt: float,
  ) -> tuple[tuple[float, ...], dict[str, float | bool | str]]:
    p = self.params
    period, ds_steps, swing_half = self._cycle_layout(control_dt)
    cycle_step = step % period

    self._update_state_from_step(step, control_dt)
    st = self.state

    if cycle_step < ds_steps:
      # 初帧で w=0 にならないよう weight に下限を設ける
      weight = (cycle_step + 1) / max(ds_steps, 1)
      action = self._double_support_action(p, weight=weight)
    elif cycle_step < ds_steps + swing_half:
      t = (cycle_step - ds_steps) / max(swing_half - 1, 1)
      action = self._swing_right_action(p, t)
    else:
      t = (cycle_step - ds_steps - swing_half) / max(swing_half - 1, 1)
      action = self._swing_left_action(p, t)

    self._apply_balance(action, obs, p)

    clipped = tuple(float(np.clip(a, -1.0, 1.0)) for a in action)
    self._prev_action = list(clipped)
    debug = {**st.to_dict(), "step": float(step)}
    return clipped, debug
