"""観測契約（biped_walk_v1）の単体テスト。"""

from __future__ import annotations

import numpy as np

import config
from contract import TELEMETRY_CONTRACT
from contract.validate import validate_obs_vector


def test_contract_validate_passes() -> None:
  TELEMETRY_CONTRACT.validate()


def test_obs_dim_matches_config() -> None:
  assert TELEMETRY_CONTRACT.observation.obs_dim == config.OBS_DIM


def test_validate_obs_rejects_wrong_dim() -> None:
  issues = validate_obs_vector(np.zeros(config.OBS_DIM - 1), TELEMETRY_CONTRACT)
  assert any("obs dim" in msg for msg in issues)


def test_validate_obs_rejects_nan() -> None:
  obs = np.zeros(config.OBS_DIM, dtype=np.float64)
  obs[0] = np.nan
  issues = validate_obs_vector(obs, TELEMETRY_CONTRACT)
  assert len(issues) > 0
