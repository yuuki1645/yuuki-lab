"""観測契約（biped_walk_v1）の単体テスト。"""

from __future__ import annotations

import numpy as np

from contract import TELEMETRY_CONTRACT
from contract.validate import validate_obs_vector


def test_contract_validate_passes() -> None:
  TELEMETRY_CONTRACT.validate()


def test_obs_dim_matches_config(default_ctx) -> None:
  assert TELEMETRY_CONTRACT.observation.obs_dim == default_ctx.cfg.sim.obs_dim


def test_validate_obs_rejects_wrong_dim(default_ctx) -> None:
  dim = default_ctx.cfg.sim.obs_dim
  issues = validate_obs_vector(np.zeros(dim - 1), TELEMETRY_CONTRACT)
  assert any("obs dim" in msg for msg in issues)


def test_validate_obs_rejects_nan(default_ctx) -> None:
  obs = np.zeros(default_ctx.cfg.sim.obs_dim, dtype=np.float64)
  obs[0] = np.nan
  issues = validate_obs_vector(obs, TELEMETRY_CONTRACT)
  assert len(issues) > 0
