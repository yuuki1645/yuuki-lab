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
  assert all(j.config_id == 1 for j in jobs)
  assert [j.seed_id for j in sorted(jobs, key=lambda j: j.seed)] == list(range(1, 11))


def test_lr_sweep_3x10_config_and_seed_ids() -> None:
  yaml_path = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "exp_026_biped_ppo_hop_balance"
    / "sweeps"
    / "lr_sweep_3x10.yaml"
  )
  spec = load_sweep_spec(yaml_path)
  jobs = expand_sweep_jobs(spec)
  assert len(jobs) == 30

  by_config: dict[int, list] = {}
  for job in jobs:
    by_config.setdefault(job.config_id, []).append(job)

  assert set(by_config.keys()) == {1, 2, 3}
  for config_id, group in by_config.items():
    assert len(group) == 10
    assert sorted(j.seed_id for j in group) == list(range(1, 11))
    assert len({j.config_hash for j in group}) == 1
    assert all("seed" not in j.config_overrides for j in group)
    assert all(j.config_overrides.get("num_updates") == 6000 for j in group)

  lr_by_config = {
    config_id: sorted({j.config_overrides["lr"] for j in group})[0]
    for config_id, group in by_config.items()
  }
  assert lr_by_config == {1: 1.0e-4, 2: 2.5e-4, 3: 5.0e-4}
