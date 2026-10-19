"""カゴと両脚の歩行。Gym ID は YuukiLab-BipedWalk-v0。"""

import gymnasium as gym

from . import agents

gym.register(
    id="YuukiLab-BipedWalk-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.biped_walk_env_cfg:BipedWalkEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:BipedWalkPPORunnerCfg",
    },
)

gym.register(
    id="YuukiLab-BipedWalk-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.biped_walk_env_cfg:BipedWalkEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:BipedWalkPPORunnerCfg",
    },
)
