# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""PPO hyperparameters for Manager-Based BipedPpoWalk (rsl-rl >= 4.0 / 5.0 形式)."""

from isaaclab.utils import configclass

from isaaclab_rl.rsl_rl import (
    RslRlMLPModelCfg,
    RslRlOnPolicyRunnerCfg,
    RslRlPpoAlgorithmCfg,
)


@configclass
class PPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 3000
    # 節目で play / eval しやすいよう短めに保存する（本番でディスクが気になる場合は戻す）
    save_interval = 10
    # Separate log dir from Direct runs
    experiment_name = "biped_ppo_walk_manager"
    logger = "wandb"
    wandb_project = "biped_ppo_walk"
    # 環境の policy 観測グループを actor / critic に明示的に割り当て（rsl-rl >= 4.0）
    obs_groups = {"actor": ["policy"], "critic": ["policy"]}
    actor = RslRlMLPModelCfg(
        hidden_dims=[256, 256, 128],
        activation="elu",
        obs_normalization=True,
        # 旧 init_noise_std=0.28 相当（rsl-rl >= 5.0 の Gaussian 出力分布）
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=0.28),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[256, 256, 128],
        activation="elu",
        obs_normalization=True,
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
