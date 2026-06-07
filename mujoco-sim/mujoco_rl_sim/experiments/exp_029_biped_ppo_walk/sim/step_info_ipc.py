"""Subproc VecEnv の Pipe 送信用に step_info を軽量化する。

telemetry 用の大きな配列（関節角リスト等）は送らず、
``EpisodeMetricsCollector`` が参照するスカラーのみ残す。
"""

from __future__ import annotations

from typing import Any


def lite_step_info(step_info: dict[str, Any]) -> dict[str, Any]:
  """IPC 向けに step_info を必要最小限の dict に絞る。"""
  return {
    "imu_x": float(step_info.get("imu_x", 0.0)),
    "imu_dx": float(step_info.get("imu_dx", 0.0)),
    "upright": float(step_info.get("upright", 0.0)),
    "foot_on_floor": float(step_info.get("foot_on_floor", 0.0)),
    "reward_forward": float(step_info.get("reward_forward", 0.0)),
    "reward_forward_imu": float(step_info.get("reward_forward_imu", 0.0)),
    "reward_forward_foot": float(step_info.get("reward_forward_foot", 0.0)),
    "reward_effort_penalty": float(step_info.get("reward_effort_penalty", 0.0)),
    "reward_shaping": float(step_info.get("reward_shaping", 0.0)),
    "reward_upright": float(step_info.get("reward_upright", 0.0)),
    "reward_push_off": float(step_info.get("reward_push_off", 0.0)),
    "reward_landing": float(step_info.get("reward_landing", 0.0)),
    "reward_backward_lean_penalty": float(
      step_info.get("reward_backward_lean_penalty", 0.0)
    ),
    "reward_forward_lean_penalty": float(
      step_info.get("reward_forward_lean_penalty", 0.0)
    ),
    "reward_height_penalty": float(step_info.get("reward_height_penalty", 0.0)),
    "reward_flight_duration_penalty": float(
      step_info.get("reward_flight_duration_penalty", 0.0)
    ),
    "reward_heading_misalign_penalty": float(
      step_info.get("reward_heading_misalign_penalty", 0.0)
    ),
    "reward_lateral_tilt_penalty": float(
      step_info.get("reward_lateral_tilt_penalty", 0.0)
    ),
    "reward_shank_step_penalty": float(
      step_info.get("reward_shank_step_penalty", 0.0)
    ),
    "reward_double_support_penalty": float(
      step_info.get("reward_double_support_penalty", 0.0)
    ),
    "reward_alternating_landing": float(
      step_info.get("reward_alternating_landing", 0.0)
    ),
    "landed": float(step_info.get("landed", 0.0)),
    "alternating_landing": float(step_info.get("alternating_landing", 0.0)),
    "single_support": float(step_info.get("single_support", 0.0)),
    "both_feet_on_floor": float(step_info.get("both_feet_on_floor", 0.0)),
    "flight_steps": float(step_info.get("flight_steps", 0.0)),
    "termination_reason": step_info.get("termination_reason"),
    "basket_contact_normal_force_n": step_info.get(
      "basket_contact_normal_force_n"
    ),
    "thigh_contact_normal_force_n": step_info.get("thigh_contact_normal_force_n"),
    "terminated": bool(step_info.get("terminated", False)),
  }
