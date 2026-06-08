"""Subproc VecEnv のスモークテスト（subprocess 経由）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_EXP_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.slow
def test_subproc_vec_env_smoke_subprocess() -> None:
  """Windows spawn 向け: 専用スクリプトを subprocess で実行する。"""
  result = subprocess.run(
    [sys.executable, "tests/subproc_vec_env_smoke_main.py"],
    cwd=_EXP_ROOT,
    capture_output=True,
    text=True,
    timeout=120,
    check=False,
  )
  assert result.returncode == 0, (
    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
  )
  assert "subproc_vec_env_smoke_ok" in result.stdout
