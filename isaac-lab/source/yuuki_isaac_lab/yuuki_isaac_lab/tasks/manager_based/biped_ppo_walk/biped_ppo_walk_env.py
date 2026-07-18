# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""BipedPpoWalk PPO task on ManagerBasedRLEnv."""

from __future__ import annotations

from collections.abc import Sequence

import torch

from isaaclab.envs import ManagerBasedRLEnv

from yuuki_isaac_lab.assets.robots.yuuki_biped.mjcf_utils import ensure_mjcf_importer_enabled

from .biped_ppo_walk_env_cfg import BipedPpoWalkEnvCfg
from .mdp.episode_state import BipedEpisodeState


class BipedPpoWalkEnv(ManagerBasedRLEnv):
    """12-DOF biped walk (+X alternating single support) on ManagerBasedRLEnv."""

    cfg: BipedPpoWalkEnvCfg

    def __init__(self, cfg: BipedPpoWalkEnvCfg, render_mode: str | None = None, **kwargs):
        # MJCF importer must be enabled before robot spawn (headless kit).
        ensure_mjcf_importer_enabled()
        super().__init__(cfg, render_mode, **kwargs)

    def load_managers(self) -> None:
        """Initialize biped episode state before observation manager probes policy terms."""
        self.biped_state = BipedEpisodeState(self)
        super().load_managers()

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

        self.biped_state.record_episode_displacement(env_ids)
        # super()._reset_idx() が episode_length_buf をゼロ化するため、終了エピソード長を先に退避する
        episode_lengths = self.episode_length_buf[env_ids].float()
        super()._reset_idx(env_ids)
        self._log_watchlist(env_ids, episode_lengths)
        self.biped_state.init_env_buffers(env_ids)
        self.biped_state._last_update_step = -1
        self.biped_state.snapshot = None

    def _log_watchlist(self, env_ids: torch.Tensor, episode_lengths: torch.Tensor) -> None:
        """重要指標を WandB の専用セクション（0_Watchlist/）にも重複ログする。

        WandB はキーの ``/`` より前をセクション名として自動グルーピングし、
        セクションはアルファベット順に並ぶため、``0_`` 接頭辞で常に最上部に表示される。
        値は既存メトリクスの複製（スカラー）なのでログコストはほぼゼロ。

        注意: super()._reset_idx() は extras["log"] を新しい dict に差し替えるため、
        このメソッドは必ず super() の後に呼ぶこと。
        """
        if env_ids.numel() == 0:
            return
        log = self.extras.setdefault("log", {})

        # 前進距離（このタスクの主目的。右上がりが好ましい）
        log["0_Watchlist/episode_displacement_x"] = self.biped_state.last_episode_displacement[env_ids].mean()
        # エピソード長（長くなる = 転倒が減る。上限は episode_length_s / step_dt）
        log["0_Watchlist/episode_length_steps"] = episode_lengths.mean()

        # 終了理由の内訳（bad_pose は下がる・time_out は後半増えるのが好ましい）
        for key in ("Episode_Termination/bad_pose", "Episode_Termination/time_out"):
            if key in log:
                log["0_Watchlist/" + key.split("/")[-1]] = log[key]

        # エピソード報酬合計（報酬だけ伸びて displacement が停滞する場合は報酬ハックを疑う）
        reward_terms = [v for k, v in log.items() if k.startswith("Episode_Reward/")]
        if reward_terms:
            log["0_Watchlist/episode_reward_total"] = sum(reward_terms)
