"""終了ペナルティ計算の単体テスト。"""

from __future__ import annotations

from sim.termination import NOT_TERMINATED, Termination


def test_not_terminated_is_inactive() -> None:
  assert NOT_TERMINATED.terminated is False
  assert NOT_TERMINATED.reason is None
  assert NOT_TERMINATED.penalty == 0.0


def test_floor_termination_penalty_increases_with_force() -> None:
  low = Termination._floor_termination_penalty(0.0)
  high = Termination._floor_termination_penalty(500.0)
  assert high < low
