# type: ignore

import time
from mujoco_rl_sim.envs.env_004 import Env004
from mujoco_rl_sim.agents.agent_001 import Agent001


NUM_EPISODES = 10
MAX_STEPS = 1000
SLEEP_TIME = 0

env = Env004()
agent = Agent001()



for episode in range(NUM_EPISODES):
  print(f"\n========= episode {episode+1}/{NUM_EPISODES} =========\n")

  obs = env.reset()

  for step in range(MAX_STEPS):
    # 行動を求める (0なら-3°、1なら3°)
    action = agent.get_action(obs)

    # 環境に行動を適用
    obs_next, reward = env.step(action)

    print(f"step: {step+1: 4d} | obs(x): {obs:10.5f} | action: {action} | reward: {reward:10.5f} | obs_next(x): {obs_next:10.5f}")

    agent.update_Q_table(obs, action, reward, obs_next)


    obs = obs_next

    time.sleep(SLEEP_TIME)


agent.save_Q_table()