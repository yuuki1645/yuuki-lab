"""チェックポイントパス検証のユニットテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mujoco_rl_sim.dispatch.common.checkpoint_paths import (
  parse_checkpoint_rel,
  resolve_checkpoint_file,
)


def test_parse_main_checkpoint_rel() -> None:
  loc = parse_checkpoint_rel("exp_027_biped_ppo_walk/my_run/final.pt")
  assert loc.exp_id == "exp_027_biped_ppo_walk"
  assert loc.run_dir == "my_run"
  assert loc.filename == "final.pt"
  assert loc.archive is False


def test_parse_archive_checkpoint_rel() -> None:
  loc = parse_checkpoint_rel("archive/exp_008_2joint_ppo_hop_shaping/old_run/update_001000.pt")
  assert loc.archive is True
  assert loc.exp_id == "exp_008_2joint_ppo_hop_shaping"
  assert loc.filename == "update_001000.pt"


def test_reject_traversal() -> None:
  with pytest.raises(ValueError):
    parse_checkpoint_rel("../secret.pt")


def test_resolve_checkpoint_file(tmp_path: Path) -> None:
  ckpt = tmp_path / "exp_a" / "run1" / "final.pt"
  ckpt.parent.mkdir(parents=True)
  ckpt.write_bytes(b"x")
  resolved = resolve_checkpoint_file(
    runs_root=tmp_path,
    checkpoint_rel="exp_a/run1/final.pt",
  )
  assert resolved == ckpt.resolve()
