"""exp_001: 2 関節脚 A2C 学習ループ。

実行例（mujoco-sim ディレクトリから）:

  python -m mujoco_rl_sim.experiments.exp_001_2joint_a2c.train
"""

import time

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.agent import AgentExp001A2C
from mujoco_rl_sim.experiments.exp_001_2joint_a2c.env import EnvExp0012JointA2C


def main() -> None:
  env = EnvExp0012JointA2C()
  agent = AgentExp001A2C(obs_dim=config.OBS_DIM)

  obs = env.reset()
  episode_step = 0
  episode_return = 0.0

  for u in range(config.NUM_UPDATES):
    for _ in range(config.ROLLOUT_STEPS):
      action, value = agent.act(obs)
      obs_next, reward, terminated = env.step(
        action,
        visualize=False,
        episode_step=episode_step,
      )

      episode_step += 1
      episode_return += reward
      done = terminated or episode_step >= config.MAX_STEPS_PER_EPISODE

      agent.store(obs, action, reward, value, done)

      obs = obs_next
      if done:
        obs = env.reset()
        episode_step = 0
        episode_return = 0.0

    stats = agent.update(obs)
    if (u + 1) % config.LOG_EVERY == 0 or u == 0:
      print(
        f"update {u + 1: 5d}/{config.NUM_UPDATES} | "
        f"mean_target: {stats['mean_target']:10.5f} | "
        f"policy_loss: {stats['policy_loss']:10.5f} | "
        f"value_loss: {stats['value_loss']:10.5f} | "
        f"entropy: {stats['entropy']:10.5f}"
      )


if __name__ == "__main__":
  main()
