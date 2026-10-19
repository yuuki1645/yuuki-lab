"""RSL-RL の方策。方策は小さく、批評家は少し大きい。"""

from isaaclab.utils.configclass import configclass

from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class BipedWalkPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    """腰の計算機でも推論できる大きさから始める。"""

    num_steps_per_env = 24
    max_iterations = 1500
    save_interval = 50
    experiment_name = "yuuki_biped_walk"
    # 学習の数値は W&B のこのプロジェクトへ送る。
    logger = "wandb"
    wandb_project = "yuuki_biped_walk"
    # policy が方策。critic グループは批評家だけが足す。
    obs_groups = {"actor": ["policy"], "critic": ["policy", "critic"]}
    actor = RslRlMLPModelCfg(
        hidden_dims=[128, 64],
        activation="elu",
        obs_normalization=True,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[256, 128],
        activation="elu",
        obs_normalization=True,
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.005,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )
