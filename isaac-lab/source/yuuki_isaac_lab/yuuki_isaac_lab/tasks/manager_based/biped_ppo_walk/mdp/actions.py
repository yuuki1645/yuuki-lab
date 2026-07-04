# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Custom action term: exp_030 neutral-offset joint position mapping."""

from __future__ import annotations

from dataclasses import MISSING
from typing import TYPE_CHECKING

import torch
from isaaclab.assets import Articulation
from isaaclab.managers.action_manager import ActionTerm
from isaaclab.managers.manager_term_cfg import ActionTermCfg
from isaaclab.utils import configclass

from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp import action as action_mdp
from yuuki_isaac_lab.tasks.direct.biped_ppo_walk.mdp.actuators import JOINT_NAMES, ctrl_ranges_tensor, neutral_pos_tensor

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedEnv


class BipedNeutralJointPositionAction(ActionTerm):
    """Map policy [-1, 1] to joint position targets via exp_030 ctrl mapping."""

    cfg: BipedNeutralJointPositionActionCfg
    _asset: Articulation

    def __init__(self, cfg: BipedNeutralJointPositionActionCfg, env: ManagerBasedEnv) -> None:
        super().__init__(cfg, env)
        self._joint_ids, self._joint_names = self._asset.find_joints(list(cfg.joint_names), preserve_order=True)
        self._num_joints = len(self._joint_ids)
        self._raw_actions = torch.zeros(self.num_envs, self.action_dim, device=self.device)
        self._processed_actions = torch.zeros_like(self._raw_actions)
        self._ctrl_lo, self._ctrl_hi = ctrl_ranges_tensor(self.device)
        self._neutral = neutral_pos_tensor(self.device)

    @property
    def action_dim(self) -> int:
        return self._num_joints

    @property
    def raw_actions(self) -> torch.Tensor:
        return self._raw_actions

    @property
    def processed_actions(self) -> torch.Tensor:
        return self._processed_actions

    def process_actions(self, actions: torch.Tensor) -> None:
        self._raw_actions[:] = actions
        self._processed_actions[:] = action_mdp.actions_to_joint_targets(
            actions, self._ctrl_lo, self._ctrl_hi, self._neutral
        )

    def apply_actions(self) -> None:
        self._asset.set_joint_position_target(self._processed_actions, joint_ids=self._joint_ids)

    def reset(self, env_ids: slice | torch.Tensor | None = None) -> None:
        self._raw_actions[env_ids] = 0.0
        self._processed_actions[env_ids] = 0.0


@configclass
class BipedNeutralJointPositionActionCfg(ActionTermCfg):
    class_type: type[ActionTerm] = BipedNeutralJointPositionAction
    asset_name: str = MISSING
    joint_names: list[str] = MISSING


DEFAULT_JOINT_NAMES = list(JOINT_NAMES)
