"""008: A2C 学習ループ（PPO の train_007 と同じ形）。

  環境1本で ROLLOUT_STEPS 分データを集め、agent.update で1ラウンド更新する。
"""

from mujoco_rl_sim.envs.env_008_a2c import Env008A2C
from mujoco_rl_sim.agents.agent_008_a2c import Agent008A2C, ROLLOUT_STEPS

import time


NUM_UPDATES = 200
# NUM_UPDATES = 1
MAX_STEPS_PER_EPISODE = 3000
# MAX_STEPS_PER_EPISODE = 10
SLEEP_TIME = 0


env = Env008A2C()
agent = Agent008A2C(obs_dim=3)

obs = env.reset()
episode_step = 0

for u in range(NUM_UPDATES):
  for _ in range(ROLLOUT_STEPS):
    action, value = agent.act(obs)
    obs_next, reward = env.step(action)

    episode_step += 1
    done = episode_step >= MAX_STEPS_PER_EPISODE

    agent.store(obs, action, reward, value, done)

    obs = obs_next
    if done:
      obs = env.reset()
      episode_step = 0

    time.sleep(SLEEP_TIME)

  stats = agent.update(obs)
  print(
    f"update {u + 1: 3d}/{NUM_UPDATES} | "
    f"mean_target: {stats['mean_target']:10.5f} | "
    f"policy_loss: {stats['policy_loss']:10.5f} | "
    f"value_loss: {stats['value_loss']:10.5f} | "
    f"entropy: {stats['entropy']:10.5f}"
  )
