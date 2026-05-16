from mujoco_rl_sim.envs.env_007_ppo import Env007PPO
from mujoco_rl_sim.agents.agent_007_ppo import Agent007PPO, ROLLOUT_STEPS

import time


# NUM_UPDATES = 500
NUM_UPDATES = 1
MAX_STEPS_PER_EPISODE = 5000
SLEEP_TIME = 0


env = Env007PPO()
agent = Agent007PPO(obs_dim=3)

obs = env.reset()
episode_step = 0

for u in range(NUM_UPDATES):
  for _ in range(ROLLOUT_STEPS):
    action, log_prob, value = agent.act(obs)
    obs_next, reward = env.step(action)

    episode_step += 1
    done = episode_step >= MAX_STEPS_PER_EPISODE

    agent.store(obs, action, reward, log_prob, value, done)

    obs = obs_next
    if done:
      obs = env.reset()
      episode_step = 0

    time.sleep(SLEEP_TIME)

  stats = agent.update(obs)
  print(
    f"update {u + 1: 3d}/{NUM_UPDATES} | "
    f"mean_return: {stats['mean_return']:10.5f} | "
    f"policy_loss: {stats['policy_loss']:10.5f} | "
    f"value_loss: {stats['value_loss']:10.5f} | "
    f"entropy: {stats['entropy']:10.5f}"
  )
