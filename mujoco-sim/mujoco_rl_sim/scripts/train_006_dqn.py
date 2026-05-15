from mujoco_rl_sim.envs.env_006_dqn import Env006DQN
from mujoco_rl_sim.agents.agent_006_dqn import Agent006DQN


NUM_EPISODES = 5
MAX_STEPS = 10


env = Env006DQN()
agent = Agent006DQN(num_states=2, num_actions=5)


for episode in range(NUM_EPISODES):
  print(f"\n========= episode {episode+1}/{NUM_EPISODES} =========\n")

  obs = env.reset()

  for step in range(MAX_STEPS):
    action = agent.get_action(obs)

    obs_next, reward = env.step(action)