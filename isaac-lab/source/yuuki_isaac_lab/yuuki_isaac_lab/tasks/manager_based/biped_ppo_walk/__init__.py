# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""Biped walk PPO task (Isaac Lab Manager-Based)."""

import gymnasium as gym

from . import agents

##
# Register Gym environments.
##

gym.register(
    id="YuukiLab-BipedPpoWalk-v0",
    entry_point=f"{__name__}.biped_ppo_walk_env:BipedPpoWalkEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.biped_ppo_walk_env_cfg:BipedPpoWalkEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:PPORunnerCfg",
    },
)

gym.register(
    id="YuukiLab-BipedPpoWalk-Play-v0",
    entry_point=f"{__name__}.biped_ppo_walk_env:BipedPpoWalkEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.biped_ppo_walk_env_cfg:BipedPpoWalkEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:PPORunnerCfg",
    },
)
