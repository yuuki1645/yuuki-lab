from mujoco_rl_sim.envs.env_004 import Env004
from mujoco_rl_sim.agents.agent_001 import Agent001



MAX_STEPS = 10



env = Env004()
agent = Agent001()



obs = env.reset()

for step in range(MAX_STEPS):
  print(f"========= step {step} =========\n")

  # 行動を求める (0なら-3°、1なら3°)
  action = agent.get_action(obs)

  # 環境に行動を適用
  obs_next = env.step(action)

  obs = obs_next