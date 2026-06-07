"""AgentPPO.act_batch の単体テスト。"""

from __future__ import annotations

import numpy as np
import torch

import config
from rl.agent import AgentPPO


def test_act_batch_shape_and_finite() -> None:
  """act_batch が [N, act_dim] の有限値を返す。"""
  torch.manual_seed(0)
  agent = AgentPPO(obs_dim=config.OBS_DIM, action_dim=config.ACTION_DIM)
  n = 3
  obs_batch = np.zeros((n, config.OBS_DIM), dtype=np.float64)

  actions, values, log_probs = agent.act_batch(obs_batch)

  assert actions.shape == (n, config.ACTION_DIM)
  assert values.shape == (n,)
  assert log_probs.shape == (n,)
  assert np.isfinite(actions).all()

