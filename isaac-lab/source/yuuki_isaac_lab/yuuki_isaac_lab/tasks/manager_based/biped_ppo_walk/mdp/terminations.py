# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Termination terms (same as Direct _get_dones)."""

from __future__ import annotations

from isaaclab.envs import ManagerBasedRLEnv

from .episode_state import ensure_step_updated, get_biped_state


def bad_pose(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Terminate when consecutive bad-pose steps exceed threshold."""
    ensure_step_updated(env)
    state = get_biped_state(env)
    return state.bad_pose_steps >= env.cfg.termination.bad_pose_consecutive_steps


def time_out(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Truncate episode at max length."""
    return env.episode_length_buf >= env.max_episode_length - 1
