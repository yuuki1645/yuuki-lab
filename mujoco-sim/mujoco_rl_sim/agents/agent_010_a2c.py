"""互換: 実装は experiments/exp_001_2joint_a2c へ移動。"""

from mujoco_rl_sim.experiments.exp_001_2joint_a2c.agent import (
  OBS_DIM,
  ROLLOUT_STEPS,
  Agent010A2C,
)

__all__ = ["Agent010A2C", "OBS_DIM", "ROLLOUT_STEPS"]
