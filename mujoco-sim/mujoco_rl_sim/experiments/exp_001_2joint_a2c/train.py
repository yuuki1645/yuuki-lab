"""exp_001: 2 関節脚 A2C 学習ループ。

実行例（mujoco-sim ディレクトリから）:

  python -m mujoco_rl_sim.experiments.exp_001_2joint_a2c.train

wandb を無効にする例:

  set WANDB_MODE=disabled
  python -m mujoco_rl_sim.experiments.exp_001_2joint_a2c.train
"""

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_001_2joint_a2c import wandb_logging
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.agent import AgentExp001A2C
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.env import EnvExp0012JointA2C


def main() -> None:
  use_wandb = wandb_logging.init()
  env = EnvExp0012JointA2C(enable_viewer=config.ENABLE_VIEWER)
  agent = AgentExp001A2C(obs_dim=config.OBS_DIM)

  obs = env.reset()
  episode_step = 0
  episode_return = 0.0
  episode_forward = 0.0
  episode_upright_sum = 0.0
  episode_foot_contact_steps = 0
  episode_index = 0
  total_env_steps = 0

  try:
    for u in range(config.NUM_UPDATES):
      for _ in range(config.ROLLOUT_STEPS):
        action, value = agent.act(obs)
        obs_next, reward, terminated, step_info = env.step(
          action,
          visualize=False,
          episode_step=episode_step,
        )

        episode_step += 1
        episode_return += reward
        episode_forward += step_info["reward_forward"]
        episode_upright_sum += step_info["upright"]
        episode_foot_contact_steps += int(step_info["foot_on_floor"] > 0.5)
        total_env_steps += 1
        truncated = episode_step >= config.MAX_STEPS_PER_EPISODE
        done = terminated or truncated

        agent.store(obs, action, reward, value, done)

        obs = obs_next
        if done:
          ep_len = float(episode_step)
          if use_wandb:
            episode_metrics: dict[str, float] = {
              "episode/return": episode_return,
              "episode/length": ep_len,
              "episode/terminated": float(terminated),
              "episode/truncated": float(truncated and not terminated),
              "episode/mean_upright": episode_upright_sum / ep_len,
              "episode/foot_contact_ratio": episode_foot_contact_steps / ep_len,
              "episode/forward_reward_sum": episode_forward,
            }
            episode_metrics.update(
              wandb_logging.episode_termination_metrics(
                terminated=terminated,
                truncated=truncated,
                reason=step_info.get("termination_reason"),
              )
            )
            wandb_logging.log(episode_metrics, step=total_env_steps)
          episode_index += 1
          obs = env.reset()
          episode_step = 0
          episode_return = 0.0
          episode_forward = 0.0
          episode_upright_sum = 0.0
          episode_foot_contact_steps = 0

      stats = agent.update(obs)
      if (u + 1) % config.LOG_EVERY == 0 or u == 0:
        print(
          f"update {u + 1: 5d}/{config.NUM_UPDATES} | "
          f"mean_target: {stats['mean_target']:10.5f} | "
          f"policy_loss: {stats['policy_loss']:10.5f} | "
          f"value_loss: {stats['value_loss']:10.5f} | "
          f"entropy: {stats['entropy']:10.5f} | "
          f"episodes: {episode_index}"
        )
        if use_wandb:
          wandb_logging.log(
            {
              "train/mean_target": stats["mean_target"],
              "train/policy_loss": stats["policy_loss"],
              "train/value_loss": stats["value_loss"],
              "train/entropy": stats["entropy"],
              "train/update": float(u + 1),
              "train/episodes_finished": float(episode_index),
            },
            step=total_env_steps,
          )
  finally:
    wandb_logging.finish()


if __name__ == "__main__":
  main()
