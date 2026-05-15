from mujoco_rl_sim.envs.env_006_dqn import Env006DQN
from mujoco_rl_sim.agents.agent_006_dqn import Agent006DQN
import time


NUM_EPISODES = 100
MAX_STEPS = 10000
SLEEP_TIME = 0


env = Env006DQN()
agent = Agent006DQN(num_states=2, num_actions=5)


for episode in range(NUM_EPISODES):
  print(f"\n========= episode {episode+1}/{NUM_EPISODES} =========\n")

  obs = env.reset()

  for step in range(MAX_STEPS):
    action = agent.get_action(obs)

    # print(f"action: {action}")

    obs_next, reward = env.step(action)

    # print(f"step: {step+1: 4d} | obs(x): {obs[0]:10.5f} | obs(pitch): {obs[1]:10.5f} | action: {action} | reward: {reward:10.5f} | obs_next(x): {obs_next[0]:10.5f} | obs_next(pitch): {obs_next[1]:10.5f}")
    print(f"step: {step+1: 4d} | obs(x): {obs[0]:10.5f} | obs(pitch): {obs[1]:10.5f} | action: {action} | reward: {reward:10.5f}")

    # メモリに経験を追加
    agent.memorize(obs, action, reward, obs_next)

    # Experience ReplayでQ関数を更新する
    agent.update_Q_function()

    obs = obs_next

    time.sleep(SLEEP_TIME)