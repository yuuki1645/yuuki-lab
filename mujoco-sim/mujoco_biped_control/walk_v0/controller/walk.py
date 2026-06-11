"""歩行制御の編集対象モジュール。

tune_forward 互換の開ループ歩容 + IMU バランス層で +X 前進を狙う。
パラメータは conf/controller.yaml。action は 12 次元 [-1, 1]（0 = stand 中立）。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

import numpy as np

from runtime.config import ControlParams
from scripts.tune_forward import make_action_fn

# MuJoCo site（exp_030 lib/actuators.py）
_IMU_SITE = "imu_site"
_LEFT_FOOT_SITE = "foot_site"
_RIGHT_FOOT_SITE = "right_foot_site"

# アクチュエータ順
_L_HIP_P, _L_KNEE, _L_ANK = 1, 2, 3
_R_HIP_P, _R_KNEE, _R_ANK = 6, 7, 8
_TORSO_ROLL, _TORSO_PITCH = 10, 11

# 観測 idx（biped_walk_v1）
_OBS_DX = 0
_OBS_GYRO_X = 1
_OBS_IMU_ZAXIS_X = 4
_OBS_IMU_UPRIGHT = 6  # imu_zaxis[2] — 転倒判定と同じ
_OBS_IMU_Z_NORM = 7
_OBS_L_CONTACT = 8
_OBS_R_CONTACT = 9


class GaitPhase(enum.Enum):
  DOUBLE_SUPPORT = "double_support"
  SWING_RIGHT = "swing_right"
  SWING_LEFT = "swing_left"


@dataclass
class ControllerState:
  phase: GaitPhase = GaitPhase.DOUBLE_SUPPORT
  subphase: float = 0.0
  phase_step: int = 0
  step_count: int = 0
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


class WalkController:
  """前進歩行：開ループ（tune_forward 同一）+ 支持脚 IMU バランス。"""

  def __init__(self, params: ControlParams | None = None):
    self.params = params or ControlParams()
    self.state = ControllerState()
    self._dx_ema: float = 0.0
    self._open_loop_fn = make_action_fn(self._to_tune_dict(self.params))
    self._emergency_hold: int = 0

  def reset(self) -> None:
    self.state = ControllerState()
    self._dx_ema = 0.0
    self._emergency_hold = 0
    self._open_loop_fn = make_action_fn(self._to_tune_dict(self.params))

  @staticmethod
  def _to_tune_dict(p: ControlParams) -> dict:
    """ControlParams → tune_forward.make_action_fn 用 dict。"""
    return {
      "hp": p.base_hip_pitch,
      "kn": p.base_knee,
      "ank": p.base_ankle_pitch,
      "tor": p.base_torso_pitch,
      "ds": p.double_support_s,
      "period": p.cycle_period_s,
      "roll": p.stance_roll,
      "rs": p.swing_roll_scale,
      "shp": p.stance_hip_delta,
      "skn": p.stance_knee_delta,
      "sank": p.stance_ankle_delta,
      "push_hp": p.push_off_hip,
      "push_kn": p.push_off_knee,
      "push_ank": p.push_off_ankle,
      "lift_hp": p.swing_lift_hip,
      "reach_hp": p.swing_reach_hip,
      "ka": p.swing_knee_amp,
      "sw_ank": p.swing_ankle_lift,
      "tor_sw": p.swing_torso_bias,
    }

  def _cycle_layout(self, control_dt: float) -> tuple[int, int, int]:
    p = self.params
    period = max(int(p.cycle_period_s / control_dt), 6)
    ds_steps = max(int(p.double_support_s / control_dt), 1)
    swing_half = max((period - ds_steps) // 2, 1)
    return period, ds_steps, swing_half

  def _update_state_from_step(self, step: int, control_dt: float) -> None:
    period, ds_steps, swing_half = self._cycle_layout(control_dt)
    cycle_step = step % period
    st = self.state
    st.cycle_index = step // period

    if cycle_step >= ds_steps + swing_half:
      st.phase = GaitPhase.SWING_LEFT
      st.phase_step = cycle_step - ds_steps - swing_half
      st.subphase = st.phase_step / max(swing_half - 1, 1)
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

    local = max(0, cycle_step - ds_steps)
    if local >= 2 * swing_half:
      st.step_count = st.cycle_index * 2 + 2
    elif local >= swing_half:
      st.step_count = st.cycle_index * 2 + 1
    else:
      st.step_count = st.cycle_index * 2

  def _foot_placement_delta(
    self,
    env: Any,
    *,
    swing_left: bool,
    subphase: float,
    p: ControlParams,
  ) -> tuple[int, float]:
    """遊脚 hip pitch 追加（負 = 前）。戻り値は (hip_idx, delta)。"""
    if subphase < 0.35 or subphase > 0.85 or env is None or p.foot_place_gain <= 0.0:
      return (-1, 0.0)
    imu_x = float(env.data.site(_IMU_SITE).xpos[0])
    foot_site = _LEFT_FOOT_SITE if swing_left else _RIGHT_FOOT_SITE
    foot_x = float(env.data.site(foot_site).xpos[0])
    err = (imu_x + p.step_length_target) - foot_x
    delta = float(np.clip(p.foot_place_gain * err, -0.05, 0.14))
    hip_idx = _L_HIP_P if swing_left else _R_HIP_P
    return (hip_idx, delta)

  def _apply_balance(
    self, action: list[float], obs: np.ndarray, p: ControlParams, env: Any
  ) -> None:
    """支持脚 IMU フィードバック。歩行中の適度な前傾はデッドバンドで許容。"""
    if obs.shape[0] <= _OBS_IMU_Z_NORM:
      return

    tilt_x = float(obs[_OBS_IMU_ZAXIS_X])
    upright = float(obs[_OBS_IMU_UPRIGHT])
    gyro_x = float(obs[_OBS_GYRO_X])
    height_n = float(obs[_OBS_IMU_Z_NORM])
    left_on = float(obs[_OBS_L_CONTACT]) > 0.5
    right_on = float(obs[_OBS_R_CONTACT]) > 0.5

    # 実 IMU 高さ [m] — imu_z 終了（0.3 m）手前で膝/足首を補正
    imu_z_m = None
    if env is not None:
      imu_z_m = float(env.data.site(_IMU_SITE).xpos[2])
    height_err = 0.0
    if imu_z_m is not None and p.balance_imu_z_target > 0.0:
      height_err = float(np.clip(p.balance_imu_z_target - imu_z_m, 0.0, 0.12))

    excess_tilt = max(0.0, tilt_x - p.balance_tilt_deadband)
    activate = 1.0
    if p.balance_upright_activate > 0.0:
      activate = float(
        np.clip((p.balance_upright_activate - upright) / 0.08, 0.0, 1.0)
      )

    ankle_corr = float(
      np.clip(
        activate
        * (-p.balance_ankle_gain * excess_tilt - p.balance_gyro_damp * gyro_x),
        -p.balance_ankle_clip,
        p.balance_ankle_clip,
      )
    )
    torso_corr = float(
      np.clip(
        activate
        * (
          -p.balance_torso_tilt_gain * excess_tilt
          + p.balance_upright_gain * (upright - p.balance_upright_target)
        ),
        -p.balance_torso_clip,
        p.balance_torso_clip,
      )
    )
    height_boost = float(
      np.clip(
        p.balance_height_gain * (0.0 - height_n) + p.balance_imu_z_gain * height_err,
        0.0,
        p.balance_height_clip,
      )
    )

    if left_on and not right_on:
      action[_L_ANK] = float(np.clip(action[_L_ANK] + ankle_corr, -1.0, 1.0))
      action[_L_HIP_P] = float(
        np.clip(action[_L_HIP_P] - p.balance_hip_follow * ankle_corr, -1.0, 1.0)
      )
      action[_L_KNEE] = float(np.clip(action[_L_KNEE] - height_boost, -1.0, 1.0))
    elif right_on and not left_on:
      action[_R_ANK] = float(np.clip(action[_R_ANK] + ankle_corr, -1.0, 1.0))
      action[_R_HIP_P] = float(
        np.clip(action[_R_HIP_P] - p.balance_hip_follow * ankle_corr, -1.0, 1.0)
      )
      action[_R_KNEE] = float(np.clip(action[_R_KNEE] - height_boost, -1.0, 1.0))

    action[_TORSO_PITCH] = float(np.clip(action[_TORSO_PITCH] + torso_corr, -1.0, 1.0))
    action[_TORSO_ROLL] = float(
      np.clip(-p.torso_roll_damp * float(obs[5]), -0.25, 0.25)
    )

  def _apply_survival_recovery(
    self, action: list[float], obs: np.ndarray, p: ControlParams
  ) -> None:
    """転倒直前に歩幅を縮めて直立を回復（長距離歩行向け）。"""
    if not p.survival_recovery_enabled or obs.shape[0] <= _OBS_IMU_UPRIGHT:
      return
    upright = float(obs[_OBS_IMU_UPRIGHT])
    if upright >= p.survival_upright_thresh:
      return
    scale = float(
      np.clip(
        (upright - p.survival_upright_floor) / 0.08,
        p.survival_hip_scale_min,
        1.0,
      )
    )
    hp = p.base_hip_pitch
    for hip_idx in (_L_HIP_P, _R_HIP_P):
      action[hip_idx] = float(np.clip(hp + (action[hip_idx] - hp) * scale, -1.0, 1.0))
    torso_boost = float(
      np.clip(p.survival_torso_gain * (p.survival_upright_thresh - upright), 0.0, 0.15)
    )
    action[_TORSO_PITCH] = float(np.clip(action[_TORSO_PITCH] + torso_boost, -1.0, 1.0))

  def _maybe_emergency_ds(
    self, action: list[float], obs: np.ndarray, p: ControlParams
  ) -> bool:
    """upright が閾値を下回ったら数 step DS 姿勢を保持。"""
    if not p.emergency_ds_enabled or obs.shape[0] <= _OBS_IMU_UPRIGHT:
      return False
    upright = float(obs[_OBS_IMU_UPRIGHT])
    if upright < p.emergency_upright_thresh:
      self._emergency_hold = max(self._emergency_hold, p.emergency_hold_steps)
    if self._emergency_hold <= 0:
      return False
    self._emergency_hold -= 1
    hp, kn, ank, tor = (
      p.base_hip_pitch,
      p.base_knee,
      p.base_ankle_pitch,
      p.base_torso_pitch + p.emergency_torso_extra,
    )
    action[:] = [0.0, hp, kn, ank, 0.0, 0.0, hp, kn, ank, 0.0, 0.0, tor]
    return True

  def compute_action(
    self,
    *,
    step: int,
    obs: np.ndarray,
    env: Any,
    control_dt: float,
  ) -> tuple[tuple[float, ...], dict[str, float | bool | str]]:
    p = self.params
    self._update_state_from_step(step, control_dt)

    action = [0.0] * 12
    if not self._maybe_emergency_ds(action, obs, p):
      # 開ループ（tune_forward と bit 一致）
      action = list(self._open_loop_fn(step, obs))

      # 足先位置補正（遊脚 hip のみ）
      st = self.state
      if st.phase == GaitPhase.SWING_RIGHT:
        _, delta = self._foot_placement_delta(
          env, swing_left=False, subphase=st.subphase, p=p
        )
        if delta:
          action[_R_HIP_P] = float(np.clip(action[_R_HIP_P] + delta, -1.0, 1.0))
      elif st.phase == GaitPhase.SWING_LEFT:
        _, delta = self._foot_placement_delta(
          env, swing_left=True, subphase=st.subphase, p=p
        )
        if delta:
          action[_L_HIP_P] = float(np.clip(action[_L_HIP_P] + delta, -1.0, 1.0))

      self._apply_balance(action, obs, p, env)
      self._apply_survival_recovery(action, obs, p)

    st = self.state
    clipped = tuple(float(np.clip(a, -1.0, 1.0)) for a in action)
    dx = float(obs[_OBS_DX]) if obs.shape[0] > _OBS_DX else 0.0
    self._dx_ema = 0.92 * self._dx_ema + 0.08 * dx
    debug = {**st.to_dict(), "step": float(step), "dx_ema": self._dx_ema}
    return clipped, debug
