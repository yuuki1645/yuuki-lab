import numpy as np
import random
import torch
import torch.nn as nn
import torch.optim as optim


EPSILON = 0.1


class Agent006DQN:
  # 今回は観測が2つ、行動が5つの予定
  def __init__(self, num_states, num_actions):
    self.num_states = num_states
    self.num_actions = num_actions

    print(f"num_states: {self.num_states}, num_actions: {self.num_actions}")

    # ニューラルネットワークを構築
    self.model = nn.Sequential(
      nn.Linear(self.num_states, 32),
      nn.ReLU(),
      nn.Linear(32, 32),
      nn.ReLU(),
      nn.Linear(32, self.num_actions),
    )

    print(f"self.model: {self.model}")

    self.optimizer = optim.Adam(self.model.parameters(), lr=0.0001)

  # 0 -> -20°, 1 -> -10°, 2 -> 0°, 3 -> 10°, 4 -> 20°
  def get_action(self, obs):
    print(f"obs: {obs}")

    obs_tensor = torch.tensor(obs, dtype=torch.float32)

    if False and np.random.uniform(0, 1) < EPSILON:
      action_index = random.randint(0, 4)
      return self._action_index_to_action(action_index)
    else:
      self.model.eval()
      with torch.no_grad():
        return self.model(obs_tensor)

  def _action_index_to_action(self, action_index):
    if action_index == 0:
      return -20.0
    elif action_index == 1:
      return -10.0
    elif action_index == 2:
      return 0.0
    elif action_index == 3:
      return 10.0
    elif action_index == 4:
      return 20.0