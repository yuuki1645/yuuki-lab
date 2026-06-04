"""チェックポイント一覧走査のユニットテスト。"""

from __future__ import annotations

from pathlib import Path

from mujoco_rl_sim.dispatch.coordinator.services.checkpoint_catalog import list_checkpoints


def _touch(path: Path) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_bytes(b"ckpt")


def test_list_checkpoints_main_and_archive(tmp_path: Path, monkeypatch) -> None:
  runs = tmp_path / "runs"
  _touch(runs / "exp_test" / "run_a" / "final.pt")
  _touch(runs / "exp_test" / "run_a" / "update_000500.pt")
  _touch(runs / "archive" / "exp_old" / "run_b" / "latest.pt")

  exp_root = tmp_path / "experiments"
  (exp_root / "exp_test").mkdir(parents=True)
  (exp_root / "exp_test" / "visualize.py").write_text("# stub\n", encoding="utf-8")
  (exp_root / "archive" / "exp_old").mkdir(parents=True)
  (exp_root / "archive" / "exp_old" / "visualize.py").write_text("# stub\n", encoding="utf-8")

  def _fake_resolve(exp_id: str, *, archive: bool = False) -> Path:
    if archive:
      return exp_root / "archive" / exp_id
    return exp_root / exp_id

  monkeypatch.setattr(
    "mujoco_rl_sim.dispatch.coordinator.services.checkpoint_catalog.resolve_experiment_dir",
    _fake_resolve,
  )

  data = list_checkpoints(runs_root=runs, limit=100)
  assert data["total"] == 3
  rels = {c["checkpoint_rel"] for c in data["checkpoints"]}
  assert "exp_test/run_a/final.pt" in rels
  assert "exp_test/run_a/update_000500.pt" in rels
  assert "archive/exp_old/run_b/latest.pt" in rels

  viz = [c for c in data["checkpoints"] if c["visualizable"]]
  assert len(viz) == 3
