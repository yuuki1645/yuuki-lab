"""exp_002: 2 関節脚 A2C 学習ループ。

実行例（mujoco-sim ディレクトリから）:

  python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.train

wandb を無効にする例:

  set WANDB_MODE=disabled
  python -m mujoco_rl_sim.experiments.exp_002_2joint_a2c.train
"""

import time

from mujoco_rl_sim.experiments.exp_002_2joint_a2c import checkpoint
from mujoco_rl_sim.experiments.exp_002_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_002_2joint_a2c import wandb_logging
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.agent import AgentExp002A2C
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.env import EnvExp0022JointA2C
from mujoco_rl_sim.experiments.exp_002_2joint_a2c.termination import REASON_CONTACT_BASKET


def main() -> None:
  use_wandb = wandb_logging.init()
  env = EnvExp0022JointA2C(enable_viewer=config.ENABLE_VIEWER)
  agent = AgentExp002A2C(obs_dim=config.OBS_DIM)

  obs = env.reset()
  episode_step = 0
  episode_return = 0.0
  episode_forward = 0.0
  episode_upright_sum = 0.0
  episode_foot_contact_steps = 0
  episode_index = 0
  total_env_steps = 0
  update_time_sum_s = 0.0
  last_update = 0
  checkpoint_run_dir = checkpoint.make_run_dir() if config.SAVE_CHECKPOINTS else None
  if checkpoint_run_dir is not None:
    print(f"[checkpoint] run dir: {checkpoint_run_dir}")

  try:
    for u in range(config.NUM_UPDATES):
      t_update_start = time.perf_counter()
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
          contact_penalty = float(step_info["reward_contact_basket_penalty"])
          contact_force_n = step_info.get("basket_contact_normal_force_n")
          if use_wandb:
            episode_metrics: dict[str, float] = {
              "episode/return": episode_return,
              "episode/length": ep_len,
              "episode/terminated": float(terminated),
              "episode/truncated": float(truncated and not terminated),
              "episode/mean_upright": episode_upright_sum / ep_len,
              "episode/foot_contact_ratio": episode_foot_contact_steps / ep_len,
              "episode/forward_reward_sum": episode_forward,
              "episode/contact_basket_penalty": contact_penalty,
              "episode/contact_basket_normal_force_n": (
                float(contact_force_n) if contact_force_n is not None else 0.0
              ),
              "episode/contact_basket_terminated": float(
                step_info.get("termination_reason") == REASON_CONTACT_BASKET
              ),
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
      last_update = u + 1
      update_time_sum_s += time.perf_counter() - t_update_start
      avg_update_s = update_time_sum_s / last_update

      if (
        checkpoint_run_dir is not None
        and config.CHECKPOINT_EVERY > 0
        and last_update % config.CHECKPOINT_EVERY == 0
      ):
        paths = checkpoint.save_agent_checkpoint(
          agent,
          run_dir=checkpoint_run_dir,
          update=last_update,
          total_env_steps=total_env_steps,
          episodes_finished=episode_index,
          numbered=True,
          latest=config.CHECKPOINT_SAVE_LATEST,
        )
        print(f"[checkpoint] saved update {last_update} -> {paths[0]}")

      if last_update % config.LOG_EVERY == 0 or u == 0:
        print(
          f"update {last_update: 5d}/{config.NUM_UPDATES} | "
          f"avg_update_s: {avg_update_s:8.3f} | "
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
              "train/update": float(last_update),
              "train/episodes_finished": float(episode_index),
            },
            step=total_env_steps,
          )
  finally:
    if (
      checkpoint_run_dir is not None
      and config.CHECKPOINT_SAVE_FINAL
      and last_update > 0
    ):
      paths = checkpoint.save_agent_checkpoint(
        agent,
        run_dir=checkpoint_run_dir,
        update=last_update,
        total_env_steps=total_env_steps,
        episodes_finished=episode_index,
        numbered=False,
        latest=False,
        final=True,
      )
      print(f"[checkpoint] saved final -> {paths[0]}")
    wandb_logging.finish()


if __name__ == "__main__":
  main()
