"""010: 2関節脚 A2C 学習ループ。

  観測 7: imu_z, foot_z, foot_xaxis[2], knee [deg], ankle [deg], com_x, com_z
  報酬: +x 方向への変位。転倒でエピソード終了。
"""

from mujoco_rl_sim.envs.env_010_a2c import Env010A2C
from mujoco_rl_sim.agents.agent_010_a2c import Agent010A2C, OBS_DIM, ROLLOUT_STEPS

import time


NUM_UPDATES = 500000
MAX_STEPS_PER_EPISODE = 5000
SLEEP_TIME = 0
LOG_EVERY = 50


env = Env010A2C()
agent = Agent010A2C(obs_dim=OBS_DIM)

obs = env.reset()
episode_step = 0
episode_return = 0.0

for u in range(NUM_UPDATES):
  for _ in range(ROLLOUT_STEPS):
    action, value = agent.act(obs)
    obs_next, reward, terminated = env.step(action, visualize=False)

    episode_step += 1
    episode_return += reward
    done = terminated or episode_step >= MAX_STEPS_PER_EPISODE

    agent.store(obs, action, reward, value, done)

    obs = obs_next
    if done:
      obs = env.reset()
      episode_step = 0
      episode_return = 0.0

    time.sleep(SLEEP_TIME)

  stats = agent.update(obs)
  if (u + 1) % LOG_EVERY == 0 or u == 0:
    print(
      f"update {u + 1: 5d}/{NUM_UPDATES} | "
      f"mean_target: {stats['mean_target']:10.5f} | "
      f"policy_loss: {stats['policy_loss']:10.5f} | "
      f"value_loss: {stats['value_loss']:10.5f} | "
      f"entropy: {stats['entropy']:10.5f}"
    )
