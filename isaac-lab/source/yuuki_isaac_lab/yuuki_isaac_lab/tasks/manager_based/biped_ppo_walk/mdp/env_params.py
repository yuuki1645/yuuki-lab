# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Observation normalization scale helpers (decoupled from env_cfg imports)."""


def get_max_dx_per_step(cfg) -> float:
    """Max IMU +X displacement per control step [m]."""
    return cfg.max_dx_per_step_base * float(cfg.decimation)


def get_max_foot_dx_per_step(cfg) -> float:
    """Max foot +X displacement per control step [m]."""
    return cfg.max_foot_dx_per_step_base * float(cfg.decimation)
