# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""BipedPpoWalk PPO task on ManagerBasedRLEnv (exp_030 port)."""

from __future__ import annotations

from collections.abc import Sequence

import torch

from isaaclab.envs import ManagerBasedRLEnv

from yuuki_isaac_lab.assets.robots.yuuki_biped.mjcf_utils import ensure_mjcf_importer_enabled

from .biped_ppo_walk_env_cfg import BipedPpoWalkEnvCfg
from .mdp.episode_state import BipedEpisodeState


class BipedPpoWalkEnv(ManagerBasedRLEnv):
    """12-DOF biped walk (+X alternating single support) on ManagerBasedRLEnv.

    Same MDP as Direct ``BipedPpoWalkEnv``, decomposed into Manager terms.
    Episode state lives in ``biped_state``; eval script attributes are mirrored.
    """

    cfg: BipedPpoWalkEnvCfg

    def __init__(self, cfg: BipedPpoWalkEnvCfg, render_mode: str | None = None, **kwargs):
        # Enable MJCF importer before spawn (required in headless kit)
        ensure_mjcf_importer_enabled()
        super().__init__(cfg, render_mode, **kwargs)
        self.biped_state = BipedEpisodeState(self)

    # --- eval_biped_walk.py / Direct compatibility ---

    @property
    def last_episode_displacement(self) -> torch.Tensor:
        return self.biped_state.last_episode_displacement

    @property
    def episode_start_imu_x(self) -> torch.Tensor:
        return self.biped_state.episode_start_imu_x

    @property
    def _last_physics(self) -> dict | None:
        return self.biped_state._last_physics

    @property
    def _last_biped_ctx(self):
        return self.biped_state._last_biped_ctx

    def _reset_idx(self, env_ids: Sequence[int]) -> None:
        """Reset manager subsystems and re-init biped episode buffers."""
        if not isinstance(env_ids, torch.Tensor):
            env_ids = torch.as_tensor(list(env_ids), device=self.device, dtype=torch.long)

        # Before reset: record displacement from latest snapshot
        self.biped_state.record_episode_displacement(env_ids)

        super()._reset_idx(env_ids)

        # After reset events: sync buffers from post-reset physics
        self.biped_state.init_env_buffers(env_ids)

        self.biped_state._last_update_step = -1
        self.biped_state.snapshot = None
