"""AgentPPO.act_batch の単体テスト。"""

from __future__ import annotations

import numpy as np
import torch

from conf.schema import build_app_config
from lib.experiment_context import build_experiment_context
from rl.agent import AgentPPO


def test_act_batch_shape_and_finite() -> None:
  """act_batch が [N, act_dim] の有限値を返す。"""
  torch.manual_seed(0)
  ctx = build_experiment_context(build_app_config())
  agent = AgentPPO(ctx)
  n = 3
  obs_batch = np.zeros((n, ctx.cfg.sim.obs_dim), dtype=np.float64)

  actions, values, log_probs = agent.act_batch(obs_batch)

  assert actions.shape == (n, ctx.cfg.sim.action_dim)
  assert values.shape == (n,)
  assert log_probs.shape == (n,)
  assert np.isfinite(actions).all()

