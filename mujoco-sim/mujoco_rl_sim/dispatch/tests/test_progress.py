"""dispatch 進捗ファイルのユニットテスト。"""

from __future__ import annotations

import json
from pathlib import Path

from mujoco_rl_sim.dispatch.common.models import JobStatus
from mujoco_rl_sim.dispatch.common.progress import (
  dispatch_progress_path_for_job,
  read_dispatch_progress,
  total_updates_from_job,
  write_dispatch_progress,
)
from mujoco_rl_sim.dispatch.common.sweep_spec import PlannedJob, SweepSpec
from mujoco_rl_sim.dispatch.coordinator.db.connection import connect
from mujoco_rl_sim.dispatch.coordinator.db.repository import DispatchRepository


def test_write_and_read_progress(tmp_path: Path, monkeypatch) -> None:
  progress_file = tmp_path / "runs" / "exp" / "run-001" / "dispatch_progress.json"
  monkeypatch.setenv("DISPATCH_RUN_ID", "run-001")
  monkeypatch.setenv("DISPATCH_PROGRESS_FILE", str(progress_file))

  write_dispatch_progress(current_update=42, total_updates=6000)

  assert progress_file.is_file()
  prog = read_dispatch_progress(progress_file, run_id="run-001")
  assert prog == {"current_update": 42, "total_updates": 6000}


def test_read_progress_rejects_wrong_run_id(tmp_path: Path) -> None:
  path = tmp_path / "dispatch_progress.json"
  path.write_text(
    json.dumps({"dispatch_run_id": "other", "current_update": 1, "total_updates": 10}),
    encoding="utf-8",
  )
  assert read_dispatch_progress(path, run_id="expected") is None


def test_total_updates_from_job() -> None:
  job = {"overrides": {"num_updates": 6000}}
  assert total_updates_from_job(job) == 6000
  assert total_updates_from_job({"overrides": {}}) is None


def test_dispatch_progress_path_for_job() -> None:
  job = {"exp_id": "exp_026_biped_ppo_hop_balance", "run_id": "abc_seed1_r0"}
  path = dispatch_progress_path_for_job(job, mujoco_rl_sim_root=Path("/root/mujoco_rl_sim"))
  assert path == Path("/root/mujoco_rl_sim/runs/exp_026_biped_ppo_hop_balance/abc_seed1_r0/dispatch_progress.json")


def test_job_heartbeat_updates_progress(tmp_path: Path) -> None:
  db = tmp_path / "test.db"
  conn = connect(db)
  repo = DispatchRepository(conn)
  repo.register_sweep(
    SweepSpec(
      sweep_id="s1",
      exp_id="exp_test",
      description="",
      shuffle_seed=0,
      seeds=(1,),
      param_grid={},
      fixed_overrides={"num_updates": 100},
    ),
    spec_path=None,
    jobs=[
      PlannedJob(
        run_id="run1",
        sweep_id="s1",
        exp_id="exp_test",
        config_hash="abc",
        seed=1,
        run_index=0,
        overrides={"num_updates": 100, "seed": 1},
        queue_position=0,
      )
    ],
  )
  job = repo.lease_next_job(worker_id="w1")
  assert job is not None
  repo.mark_running(job["run_id"], worker_id="w1")
  assert repo.refresh_job_lease(
    job["run_id"],
    worker_id="w1",
    current_update=10,
    total_updates=100,
  )
  updated = repo.get_job(job["run_id"])
  assert updated is not None
  assert updated["current_update"] == 10
  assert updated["total_updates"] == 100
  assert updated["progress_updated_at"] is not None

  assert repo.refresh_job_lease(job["run_id"], worker_id="w1", current_update=5)
  updated = repo.get_job(job["run_id"])
  assert updated is not None
  assert updated["current_update"] == 10

  repo.complete_job(job["run_id"], worker_id="w1", primary_metric=1.0, artifact_path=None, git_commit=None)
  done = repo.get_job(job["run_id"])
  assert done is not None
  assert done["status"] == JobStatus.SUCCEEDED.value
  assert done["current_update"] == 100
