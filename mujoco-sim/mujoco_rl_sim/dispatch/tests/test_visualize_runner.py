"""visualize 起動コマンドのユニットテスト。"""

from __future__ import annotations

from pathlib import Path

from mujoco_rl_sim.dispatch.coordinator.services.visualize_runner import VisualizeRunner


def test_build_command_includes_stochastic(tmp_path: Path) -> None:
  runner = VisualizeRunner(runs_root=tmp_path, python_executable="/usr/bin/python3")
  exp = tmp_path / "exp_test"
  exp.mkdir()
  ckpt = tmp_path / "runs" / "exp_test" / "r1" / "final.pt"
  ckpt.parent.mkdir(parents=True)
  ckpt.write_bytes(b"x")

  cmd = runner.build_command(exp_path=exp, checkpoint_abs=ckpt)
  assert cmd[0] == "/usr/bin/python3"
  assert cmd[1] == "visualize.py"
  assert "--checkpoint" in cmd
  assert str(ckpt.resolve()) in cmd
  assert "--stochastic" in cmd
