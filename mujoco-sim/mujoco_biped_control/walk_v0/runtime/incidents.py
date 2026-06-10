"""インシデント検出 — AI が問題瞬間を特定しやすくする。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from runtime.config import IncidentConfig


@dataclass
class IncidentRecord:
  step: int
  time_s: float
  reason: str
  severity: str
  metrics: dict[str, float]
  controller_debug: dict[str, float | bool] = field(default_factory=dict)
  snapshot_dir: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


class IncidentDetector:
  def __init__(self, cfg: IncidentConfig):
    self._cfg = cfg
    self._records: list[IncidentRecord] = []
    self._last_record_step = -10_000

  @property
  def records(self) -> list[IncidentRecord]:
    return list(self._records)

  def _cooldown_ok(self, step: int) -> bool:
    return step - self._last_record_step >= self._cfg.record_cooldown_steps

  def _add(
    self,
    *,
    step: int,
    time_s: float,
    reason: str,
    severity: str,
    metrics: dict[str, float],
    controller_debug: dict[str, float | bool],
  ) -> IncidentRecord | None:
    if not self._cfg.enabled or not self._cooldown_ok(step):
      return None
    rec = IncidentRecord(
      step=step,
      time_s=time_s,
      reason=reason,
      severity=severity,
      metrics=metrics,
      controller_debug=dict(controller_debug),
    )
    self._records.append(rec)
    self._last_record_step = step
    return rec

  def observe_step(
    self,
    *,
    step: int,
    time_s: float,
    step_info: dict[str, Any],
    controller_debug: dict[str, float | bool],
    terminated: bool,
    termination_reason: str | None,
  ) -> IncidentRecord | None:
    """1 制御ステップ後に呼ぶ。インシデントがあれば記録。"""
    metrics = {
      "imu_x": float(step_info.get("imu_x", 0.0)),
      "imu_dx": float(step_info.get("imu_dx", 0.0)),
      "upright": float(step_info.get("upright", 0.0)),
      "imu_z": float(step_info.get("torso_height", 0.0)),
      "aerial_steps": float(step_info.get("aerial_steps", 0.0)),
      "single_support": float(step_info.get("single_support", 0.0)),
    }

    if terminated and termination_reason:
      return self._add(
        step=step,
        time_s=time_s,
        reason=f"terminated:{termination_reason}",
        severity="critical",
        metrics=metrics,
        controller_debug=controller_debug,
      )

    if metrics["upright"] < self._cfg.min_upright:
      return self._add(
        step=step,
        time_s=time_s,
        reason="low_upright",
        severity="warning",
        metrics=metrics,
        controller_debug=controller_debug,
      )

    if metrics.get("imu_z", 1.0) < self._cfg.min_imu_z:
      return self._add(
        step=step,
        time_s=time_s,
        reason="low_imu_z",
        severity="warning",
        metrics=metrics,
        controller_debug=controller_debug,
      )

    if metrics["aerial_steps"] > self._cfg.max_aerial_steps:
      return self._add(
        step=step,
        time_s=time_s,
        reason="prolonged_flight",
        severity="warning",
        metrics=metrics,
        controller_debug=controller_debug,
      )

    if metrics["imu_dx"] < self._cfg.min_forward_dx_per_step:
      return self._add(
        step=step,
        time_s=time_s,
        reason="backward_or_stall",
        severity="info",
        metrics=metrics,
        controller_debug=controller_debug,
      )

    return None
