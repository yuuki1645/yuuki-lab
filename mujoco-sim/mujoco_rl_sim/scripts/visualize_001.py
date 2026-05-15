# type: ignore


from mujoco_rl_sim.envs.env_004 import Env004
from mujoco_rl_sim.agents.agent_001 import Agent001


env = Env004()

agent = Agent001()
agent.load_Q_table()

obs = env.reset()

step = 0

while True:
    action = agent.get_action(obs)
    obs_next, reward = env.step(action, visualize=True)
    print(f"step: {step+1: 4d} | obs(x): {obs:10.5f} | action: {action} | reward: {reward:10.5f} | obs_next(x): {obs_next:10.5f}")
    step += 1
    obs = obs_next