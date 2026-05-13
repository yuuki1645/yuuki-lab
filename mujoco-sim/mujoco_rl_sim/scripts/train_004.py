# type: ignore

import sys
import time
from mujoco_rl_sim.envs.env_004 import Env004
from mujoco_rl_sim.agents.agent_001 import Agent001



MAX_STEPS = int(sys.argv[1])



env = Env004()
agent = Agent001()



obs = env.reset()

for step in range(MAX_STEPS):
  print(f"========= step {step} =========")
  print(f"obs: {obs}")

  # 行動を求める (0なら-3°、1なら3°)
  action = agent.get_action(obs)
  print(f"action: {action}")

  # 環境に行動を適用
  obs_next, reward = env.step(action)
  print(f"obs_next: {obs_next}")
  print(f"reward: {reward}")

  agent.update_Q_table(obs, action, reward, obs_next)


  obs = obs_next

  time.sleep(float(sys.argv[2]))