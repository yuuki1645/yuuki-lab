# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore

"""exp_030 PPO ハイパーパラメータ（conf/ppo/default.yaml 由来、rsl-rl >= 4.0 / 5.0 形式）。

    v27: v25 ckpt から fine-tune（displacement_progress 強化）。
"""

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
    experiment_name = "biped_ppo_walk"
    # 学習メトリクスは WandB に記録（--logger tensorboard で上書き可能）
    logger = "wandb"
    wandb_project = "biped_ppo_walk"
    obs_groups = {"actor": ["policy"], "critic": ["policy"]}
    actor = RslRlMLPModelCfg(
        hidden_dims=[256, 256, 128],
        activation="elu",
        obs_normalization=True,
        # v23: 探索をさらに抑えて fine-tune 安定化（旧 init_noise_std=0.28）
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
