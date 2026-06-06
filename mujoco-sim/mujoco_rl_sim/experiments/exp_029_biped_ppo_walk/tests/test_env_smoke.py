"""MuJoCo 環境の軽量スモーク（reset 1 回）。"""

from __future__ import annotations

import config
import pytest
from contract import TELEMETRY_CONTRACT
from contract.validate import assert_obs_vector
from sim.env import EnvBipedPPO


@pytest.mark.slow
def test_env_reset_obs_matches_contract() -> None:
  env = EnvBipedPPO(enable_viewer=False)
  try:
    obs = env.reset()
    assert len(obs) == config.OBS_DIM
    assert_obs_vector(obs, TELEMETRY_CONTRACT)
  finally:
    if env.viewer is not None:
      env.viewer.close()
