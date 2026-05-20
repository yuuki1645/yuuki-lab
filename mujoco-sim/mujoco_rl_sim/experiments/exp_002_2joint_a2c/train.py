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


def main() -> None:
  wandb_logging.init()
  episode_metrics = wandb_logging.episode_collector()
  env = EnvExp0022JointA2C(enable_viewer=config.ENABLE_VIEWER)
  agent = AgentExp002A2C(obs_dim=config.OBS_DIM)

  obs = env.reset()
  episode_step = 0
  episode_index = 0
  total_env_steps = 0
  update_time_sum_s = 0.0
  last_update = 0
  checkpoint_run_dir = checkpoint.make_run_dir() if config.SAVE_CHECKPOINTS else None
  if checkpoint_run_dir is not None:
    print(f"[checkpoint] run dir: {checkpoint_run_dir}")

  try:
    # 外側: 方策更新（1 update = ROLLOUT_STEPS 環境ステップ分の on-policy データ）
    for u in range(config.NUM_UPDATES):
      t_update_start = time.perf_counter()
      # 内側: ロールアウト収集 → agent.store。エピソードは env 側で区切らず連続
      for _ in range(config.ROLLOUT_STEPS):
        action, value = agent.act(obs)
        obs_next, reward, terminated, step_info = env.step(
          action,
          visualize=False,
          episode_step=episode_step,
        )

        episode_step += 1
        total_env_steps += 1
        episode_metrics.on_step(reward, step_info)
        # truncated は env から来ない。最大ステップ到達は train 側で done に含める
        truncated = episode_step >= config.MAX_STEPS_PER_EPISODE
        done = terminated or truncated

        agent.store(obs, action, reward, value, done)

        obs = obs_next
        if done:
          episode_metrics.on_episode_end(
            episode_step=episode_step,
            terminated=terminated,
            truncated=truncated,
            step_info=step_info,
            env_step=total_env_steps,
          )
          episode_index += 1
          obs = env.reset()
          episode_step = 0

      # ブートストラップ用にロールアウト直後の obs で V(s') を計算
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
        wandb_logging.log_train_update(
          stats,
          update=last_update,
          episodes_finished=episode_index,
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
