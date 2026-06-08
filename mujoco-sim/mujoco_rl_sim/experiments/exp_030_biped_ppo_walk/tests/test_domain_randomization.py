"""学習時 Domain Randomization の単体テスト。"""

from __future__ import annotations

import mujoco
import numpy as np

from sim.domain_randomization import (
  TrainingDomainRandomization,
  make_episode_dr_rng,
)
from sim.env import EnvBipedPPO


def test_make_episode_dr_rng_is_deterministic() -> None:
  r1 = make_episode_dr_rng(42, 3)
  r2 = make_episode_dr_rng(42, 3)
  assert r1.random() == r2.random()
  r3 = make_episode_dr_rng(42, 4)
  assert r1.random() != r3.random()


def test_apply_changes_friction_and_restores_nominal(default_ctx) -> None:
  model = mujoco.MjModel.from_xml_path(default_ctx.xml_path)
  data = mujoco.MjData(model)
  dr = TrainingDomainRandomization(model, default_ctx)
  foot_id = int(model.geom("foot_plate").id)
  nominal = float(model.geom_friction[foot_id, 0])

  rng = np.random.default_rng(0)
  stand_key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
  mujoco.mj_resetDataKeyframe(model, data, stand_key)
  dr.apply_for_episode(model, data, rng=rng)
  assert model.geom_friction[foot_id, 0] != nominal

  dr.restore_nominal(model)
  assert model.geom_friction[foot_id, 0] == nominal


def test_reset_eval_path_restores_after_training_dr(default_ctx) -> None:
  env = EnvBipedPPO(
    default_ctx,
    enable_viewer=False,
    training_dr_enabled=True,
    training_seed=7,
  )
  model = env.model
  foot_id = int(model.geom("foot_plate").id)
  nominal = float(model.geom_friction[foot_id, 0])

  env.reset(episode_index=0)
  assert model.geom_friction[foot_id, 0] != nominal

  eval_rng = np.random.default_rng(101)
  env.reset_eval(eval_rng)
  assert model.geom_friction[foot_id, 0] == nominal
