# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Shared scale helpers for observation normalization."""


def get_max_dx_per_step(obs_cfg, decimation: int) -> float:
    """Max IMU +X displacement per control step [m]."""
    return obs_cfg.max_dx_per_step_base * float(decimation)


def get_max_foot_dx_per_step(obs_cfg, decimation: int) -> float:
    """Max foot +X displacement per control step [m]."""
    return obs_cfg.max_foot_dx_per_step_base * float(decimation)
