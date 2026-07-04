# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""CLI helpers for GUI robot visualization (no Isaac Sim imports).

Must live outside yuuki_isaac_lab so it can be imported before SimulationApp starts.
"""

from __future__ import annotations

import argparse
from typing import Any


def add_robot_visualization_cli_args(parser: argparse.ArgumentParser) -> None:
    """Register --visualize-robots on the argument parser."""
    parser.add_argument(
        "--visualize-robots",
        action="store_true",
        default=False,
        help=(
            "Show full robot meshes in all parallel envs (sets replicate_physics=False, "
            "clone_in_fabric=False). Keeps sim.use_fabric enabled so physics/GUI stay in sync."
        ),
    )


def apply_robot_visualization_if_requested(env_cfg: Any, args_cli: argparse.Namespace) -> bool:
    """Apply visualization overrides when CLI flags are set."""
    changed = False

    if getattr(args_cli, "visualize_robots", False):
        # Play 環境 (BipedPpoWalkEnvCfg_PLAY) と同じ clone 設定のみ変更する
        env_cfg.scene.replicate_physics = False
        env_cfg.scene.clone_in_fabric = False
        changed = True
        print(
            "[INFO] Robot mesh visualization enabled: "
            "replicate_physics=False, clone_in_fabric=False (sim.use_fabric unchanged)"
        )
        num_envs = env_cfg.scene.num_envs
        if num_envs > 64:
            print(
                f"[WARN] visualize-robots with num_envs={num_envs} may take a long time to spawn. "
                "Consider --num_envs 16 for GUI debugging."
            )

    if getattr(args_cli, "disable_fabric", False):
        # USD I/O モード。GUI では viewport 更新が止まることがあるため visualize-robots とは別扱い
        env_cfg.sim.use_fabric = False
        changed = True
        print(
            "[WARN] sim.use_fabric=False (disable_fabric): physics may run but the GUI viewport "
            "can appear frozen. For mesh visibility during training, use --visualize-robots only."
        )

    return changed
