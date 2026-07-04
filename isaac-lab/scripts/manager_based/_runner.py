# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Shared runner for Manager-Based BipedPpoWalk scripts."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_ISAAC_LAB_ROOT = Path(__file__).resolve().parents[1]


def _run_script(relative_path: Path, default_task: str, argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--task" not in args:
        args = ["--task", default_task, *args]
    script_path = _ISAAC_LAB_ROOT / relative_path
    sys.argv = [str(script_path), *args]
    runpy.run_path(str(script_path), run_name="__main__")


def train_main() -> None:
    _run_script(Path("scripts/rsl_rl/train.py"), "YuukiLab-BipedPpoWalk-v0")


def play_main() -> None:
    _run_script(Path("scripts/rsl_rl/play.py"), "YuukiLab-BipedPpoWalk-Play-v0")


def eval_main() -> None:
    _run_script(Path("scripts/eval_biped_walk.py"), "YuukiLab-BipedPpoWalk-v0")


def smoke_main() -> None:
    _run_script(Path("scripts/smoke_biped_walk.py"), "YuukiLab-BipedPpoWalk-v0")
