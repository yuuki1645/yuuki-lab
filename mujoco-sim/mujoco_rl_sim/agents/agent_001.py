# type: ignore

import random
import numpy as np

ETA = 0.5
GAMMA = 0.99
EPSILON = 0.1
class Agent001:
  def __init__(self):
    self.Q_table = np.random.uniform(low=0, high=1, size=(6, 2))
    print(f"self.Q_table: {self.Q_table}")

  # 行動を求める (0なら-3°、1なら3°)
  def get_action(self, obs):
    state = self._obs_to_state(obs)
    if np.random.rand() < EPSILON:
      return random.randint(0, 1)
    else:
      return np.argmax(self.Q_table[state][:])

  def update_Q_table(self, obs, action, reward, obs_next):
    state = self._obs_to_state(obs)
    state_next = self._obs_to_state(obs_next)
    max_Q_next = max(self.Q_table[state_next][:])
    self.Q_table[state, action] = self.Q_table[state, action] + \
      ETA * (reward + GAMMA * max_Q_next - self.Q_table[state, action])

  def save_Q_table(self):
    np.save("Q_table.npy", self.Q_table)

  def load_Q_table(self):
    self.Q_table = np.load("Q_table.npy")

  def _obs_to_state(self, obs):
    # 今のところobsはX座標
    x = obs
    if x > 0.2:
      return 5
    elif x > 0.1:
      return 4
    elif x > 0.0:
      return 3
    elif x > -0.1:
      return 2
    elif x > -0.2:
      return 1
    else:
      return 0
