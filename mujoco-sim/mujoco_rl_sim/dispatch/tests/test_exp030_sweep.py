"""exp_030 sweep YAML のジョブ数回帰。"""

from __future__ import annotations

from pathlib import Path

from mujoco_rl_sim.dispatch.common.sweep_spec import expand_sweep_jobs, load_sweep_spec


def test_walk_reward_sweep_48_job_count() -> None:
  yaml_path = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "exp_030_biped_ppo_walk"
    / "sweeps"
    / "walk_reward_sweep_48.yaml"
  )
  spec = load_sweep_spec(yaml_path)
  jobs = expand_sweep_jobs(spec)
  assert len(jobs) == 48
  assert len({j.run_id for j in jobs}) == 48
  assert sorted({j.seed for j in jobs}) == [1, 2, 3, 4]
