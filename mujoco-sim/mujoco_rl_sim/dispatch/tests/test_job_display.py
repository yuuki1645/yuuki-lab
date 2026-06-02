"""job display フィールドのユニットテスト。"""

from __future__ import annotations

import json

from mujoco_rl_sim.dispatch.common.job_display import enrich_jobs_display_fields
from mujoco_rl_sim.dispatch.common.sweep_spec import expand_sweep_jobs, load_sweep_spec
from mujoco_rl_sim.dispatch.coordinator.db.connection import connect
from mujoco_rl_sim.dispatch.coordinator.db.repository import DispatchRepository
from pathlib import Path


def test_register_sweep_persists_config_ids(tmp_path: Path) -> None:
  yaml_path = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "exp_026_biped_ppo_hop_balance"
    / "sweeps"
    / "lr_sweep_3x10.yaml"
  )
  spec = load_sweep_spec(yaml_path)
  jobs = expand_sweep_jobs(spec)

  conn = connect(tmp_path / "coord.db")
  repo = DispatchRepository(conn)
  repo.register_sweep(spec, spec_path=str(yaml_path), jobs=jobs)

  stored = repo.list_jobs(sweep_id=spec.sweep_id, limit=1000)
  assert len(stored) == 30
  assert all(row["config_id"] is not None for row in stored)
  assert all(row["seed_id"] is not None for row in stored)
  assert all(isinstance(row["config_overrides"], dict) for row in stored)
  assert all("seed" not in row["config_overrides"] for row in stored)


def test_enrich_legacy_jobs_without_config_ids() -> None:
  jobs = [
    {
      "sweep_id": "s1",
      "config_hash": "cfg_a",
      "seed": 2,
      "run_index": 1,
      "overrides": {"lr": 1e-4, "seed": 2, "num_updates": 100},
      "config_id": None,
      "config_overrides_json": None,
    },
    {
      "sweep_id": "s1",
      "config_hash": "cfg_a",
      "seed": 1,
      "run_index": 0,
      "overrides": {"lr": 1e-4, "seed": 1, "num_updates": 100},
      "config_id": None,
      "config_overrides_json": None,
    },
    {
      "sweep_id": "s1",
      "config_hash": "cfg_b",
      "seed": 1,
      "run_index": 2,
      "overrides": {"lr": 2e-4, "seed": 1, "num_updates": 100},
      "config_id": None,
      "config_overrides_json": json.dumps({"lr": 2e-4, "num_updates": 100}),
    },
  ]
  enrich_jobs_display_fields(jobs)
  assert jobs[0]["config_id"] == 1
  assert jobs[1]["config_id"] == 1
  assert jobs[2]["config_id"] == 2
  assert jobs[1]["seed_id"] == 1
  assert jobs[0]["seed_id"] == 2
  assert jobs[2]["seed_id"] == 1
