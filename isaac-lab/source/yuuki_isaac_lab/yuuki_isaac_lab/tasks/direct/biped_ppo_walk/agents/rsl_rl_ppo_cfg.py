# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""exp_030 PPO ハイパーパラメータ（conf/ppo/default.yaml 由来）。

v24: v23 ckpt から fine-tune（max 3000 iter/run）。
"""

from isaaclab.utils import configclass

from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlPpoActorCriticCfg, RslRlPpoAlgorithmCfg


@configclass
class PPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 3000
    save_interval = 400
    experiment_name = "biped_ppo_walk"
    # 学習メトリクスは WandB に記録（--logger tensorboard で上書き可能）
    logger = "wandb"
    wandb_project = "biped_ppo_walk"
    empirical_normalization = True

    policy = RslRlPpoActorCriticCfg(
        # v23: 探索をさらに抑えて fine-tune 安定化（v22 で std が 0.59 まで増大）
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
        # v17: entropy を下げて学習可能な std に収束させる（v16 では std>11 に発散）
        entropy_coef=0.003,
        num_learning_epochs=8,
        num_mini_batches=32,
        learning_rate=1.2e-4,
        schedule="adaptive",
        # exp_030: gamma_per_physics_step=0.99, decimation=10 → 0.99^10
        gamma=0.904,
        lam=0.95,
        desired_kl=0.02,
        max_grad_norm=0.5,
    )
