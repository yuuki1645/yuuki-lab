"""009: 2関節脚 A2C 学習ループ。

  観測 6: knee, ankle, imu_z, foot_zaxis (x,y,z)
  行動 2: knee_servo, ankle_servo 目標角（[-1,1] -> ctrl [rad]）
"""

from mujoco_rl_sim.envs.env_009_a2c import Env009A2C
from mujoco_rl_sim.agents.agent_009_a2c import Agent009A2C, OBS_DIM, ROLLOUT_STEPS

import time


NUM_UPDATES = 50000
MAX_STEPS_PER_EPISODE = 5000
SLEEP_TIME = 0


env = Env009A2C()
agent = Agent009A2C(obs_dim=OBS_DIM)

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
