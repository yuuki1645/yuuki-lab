"""sweep YAML からジョブ登録。"""

from __future__ import annotations

from pathlib import Path

from mujoco_rl_sim.dispatch.common.sweep_spec import expand_sweep_jobs, load_sweep_spec
from mujoco_rl_sim.dispatch.coordinator.db.repository import DispatchRepository
from mujoco_rl_sim.dispatch.paths import experiment_dir


def register_sweep_file(repo: DispatchRepository, path: Path) -> dict:
  spec = load_sweep_spec(path)
  experiment_dir(spec.exp_id)
  jobs = expand_sweep_jobs(spec)
  n = repo.register_sweep(spec, spec_path=str(path), jobs=jobs)
  return {
    "sweep_id": spec.sweep_id,
    "exp_id": spec.exp_id,
    "jobs_registered": n,
    "shuffle_seed": spec.shuffle_seed,
  }


def plan_sweep_file(path: Path) -> dict:
  spec = load_sweep_spec(path)
  experiment_dir(spec.exp_id)
  jobs = expand_sweep_jobs(spec)
  return {
    "sweep_id": spec.sweep_id,
    "exp_id": spec.exp_id,
    "job_count": len(jobs),
    "shuffle_seed": spec.shuffle_seed,
    "first_jobs": [j.run_id for j in jobs[:5]],
  }
