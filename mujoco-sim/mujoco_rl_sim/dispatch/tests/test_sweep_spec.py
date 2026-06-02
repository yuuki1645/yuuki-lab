"""sweep 展開の単体テスト。"""

from __future__ import annotations

from pathlib import Path

from mujoco_rl_sim.dispatch.common.sweep_spec import expand_sweep_jobs, load_sweep_spec


def test_baseline_10seed_job_count() -> None:
  yaml_path = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "exp_026_biped_ppo_hop_balance"
    / "sweeps"
    / "baseline_10seed.yaml"
  )
  spec = load_sweep_spec(yaml_path)
  jobs = expand_sweep_jobs(spec)
  assert len(jobs) == 10
  assert len({j.run_id for j in jobs}) == 10
  assert jobs[0].queue_position == 0
  assert jobs[-1].queue_position == 9
