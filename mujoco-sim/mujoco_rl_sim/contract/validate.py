"""観測ベクトルが契約レイアウトと一致するか検証。"""

from __future__ import annotations

import numpy as np

from mujoco_rl_sim.contract.spec import ObservationSpec, TelemetryContract


def validate_obs_vector(
  obs_vector: tuple[float, ...] | list[float] | np.ndarray,
  contract: TelemetryContract,
) -> list[str]:
  """不一致があればメッセージのリストを返す（空なら OK）。"""
  issues: list[str] = []
  o = np.asarray(obs_vector, dtype=np.float64).reshape(-1)
  spec = contract.observation
  if o.size != spec.obs_dim:
    issues.append(f"obs dim: got {o.size}, expected {spec.obs_dim}")
    return issues
  for s in spec.slices:
    chunk = o[s.start : s.end]
    if not np.all(np.isfinite(chunk)):
      issues.append(f"{s.telemetry_key}: non-finite values")
  return issues


def assert_obs_vector(
  obs_vector: tuple[float, ...] | list[float] | np.ndarray,
  contract: TelemetryContract,
) -> None:
  issues = validate_obs_vector(obs_vector, contract)
  if issues:
    raise ValueError("observation contract mismatch: " + "; ".join(issues))
