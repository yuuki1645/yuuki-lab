# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""PPO hyperparameters for Manager-Based BipedPpoWalk."""

from isaaclab.utils import configclass

from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlPpoActorCriticCfg, RslRlPpoAlgorithmCfg


@configclass
class PPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 3000
    save_interval = 400
    # Separate log dir from Direct runs
    experiment_name = "biped_ppo_walk_manager"
    logger = "wandb"
    wandb_project = "biped_ppo_walk"
    empirical_normalization = True

    policy = RslRlPpoActorCriticCfg(
        init_noise_std=0.28,
        actor_obs_normalization=True,
        critic_obs_normalization=True,
        actor_hidden_dims=[256, 256, 128],
        critic_hidden_dims=[256, 256, 128],
        activation="elu",
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.003,
        num_learning_epochs=8,
        num_mini_batches=32,
        learning_rate=1.2e-4,
        schedule="adaptive",
        gamma=0.904,
        lam=0.95,
        desired_kl=0.02,
        max_grad_norm=0.5,
    )
