import numpy as np
import random
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F


EPSILON = 0.1
CAPACITY = 10000
# BATCH_SIZE = 32
BATCH_SIZE = 4
GAMMA = 0.99


class ReplayMemory:
  def __init__(self, capacity):
    self.capacity = capacity
    self.memory = []
    self.index = 0

  def push(self, obs, action, reward, obs_next):
    if len(self.memory) < self.capacity:
      self.memory.append(None)
    
    self.memory[self.index] = (obs, action, reward, obs_next)
    self.index = (self.index + 1) % self.capacity

  def sample(self, batch_size):
    return random.sample(self.memory, batch_size)

  def __len__(self):
    return len(self.memory)


class Agent006DQN:
  # 今回は観測が2つ、行動が5つの予定
  def __init__(self, num_states, num_actions):
    self.num_states = num_states
    self.num_actions = num_actions

    print(f"num_states: {self.num_states}, num_actions: {self.num_actions}")

    self.memory = ReplayMemory(capacity=CAPACITY)

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
    # print(f"obs: {obs}")

    obs_tensor = torch.tensor(obs, dtype=torch.float32)

    if False and np.random.uniform(0, 1) < EPSILON:
      action_index = random.randint(0, 4)
      return self._action_index_to_action(action_index)
    else:
      self.model.eval()
      with torch.no_grad():
        action_index = self.model(obs_tensor).argmax().item()
        return self._action_index_to_action(action_index)

  def memorize(self, obs, action, reward, obs_next):
    action_index = self._action_deg_to_index(action)
    self.memory.push(obs, action_index, reward, obs_next)

  # Experience ReplayでQ関数を更新する
  def update_Q_function(self):
    if len(self.memory) < BATCH_SIZE:
      return

    batch = self.memory.sample(BATCH_SIZE)

    obs_batch = torch.tensor([obs for obs, _, _, _ in batch], dtype=torch.float32)
    action_batch = torch.tensor([action for _, action, _, _ in batch], dtype=torch.int64)
    reward_batch = torch.tensor([reward for _, _, reward, _ in batch], dtype=torch.float32)
    obs_next_batch = torch.tensor([obs_next for _, _, _, obs_next in batch], dtype=torch.float32)

    with torch.no_grad():
      self.model.eval()
      max_q_values_next_batch = self.model(obs_next_batch).max(dim=1)[0]

    expected_q_values = reward_batch + GAMMA * max_q_values_next_batch

    self.model.train()
    q_values = self.model(obs_batch)
    q_value = q_values.gather(1, action_batch.unsqueeze(1)).squeeze(1)

    loss = F.smooth_l1_loss(q_value, expected_q_values)

    self.optimizer.zero_grad()
    loss.backward()
    self.optimizer.step()

  def _action_deg_to_index(self, action_deg: float) -> int:
    action_map = {-20.0: 0, -10.0: 1, 0.0: 2, 10.0: 3, 20.0: 4}
    return action_map[action_deg]

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