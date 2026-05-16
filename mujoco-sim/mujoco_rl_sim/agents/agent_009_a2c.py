"""009: 2関節脚用 A2C — 008 と同じ更新ロジック、観測9次元・行動2次元。"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim


GAMMA = 0.99
LR = 3e-4
ROLLOUT_STEPS = 512
VALUE_COEF = 0.5
ENTROPY_COEF = 0.01
MAX_GRAD_NORM = 0.5
MINIBATCH_SIZE = 256

OBS_DIM = 9
ACTION_DIM = 2


class Actor(nn.Module):
  """観測 -> 2次元ガウス方策の平均。標準偏差は行動次元ごとに学習。"""

  def __init__(self, obs_dim, action_dim):
    super().__init__()
    self.action_dim = action_dim
    self.net = nn.Sequential(
      nn.Linear(obs_dim, 64),
      nn.ReLU(),
      nn.Linear(64, 64),
      nn.ReLU(),
      nn.Linear(64, action_dim),
      nn.Tanh(),
    )
    self.log_std = nn.Parameter(torch.zeros(action_dim))

  def forward(self, obs):
    mean = self.net(obs)
    std = self.log_std.exp().expand_as(mean).clamp(min=1e-6)
    return mean, std


class Critic(nn.Module):
  def __init__(self, obs_dim):
    super().__init__()
    self.net = nn.Sequential(
      nn.Linear(obs_dim, 64),
      nn.ReLU(),
      nn.Linear(64, 64),
      nn.ReLU(),
      nn.Linear(64, 1),
    )

  def forward(self, obs):
    return self.net(obs).squeeze(-1)


class Agent009A2C:
  def __init__(self, obs_dim=OBS_DIM, action_dim=ACTION_DIM):
    self.obs_dim = obs_dim
    self.action_dim = action_dim
    print(f"[A2C-009] obs_dim={self.obs_dim}, action_dim={self.action_dim} (continuous)")

    self.actor = Actor(obs_dim, action_dim)
    self.critic = Critic(obs_dim)

    self.optimizer = optim.Adam(
      list(self.actor.parameters()) + list(self.critic.parameters()),
      lr=LR,
    )

    self._reset_rollout_storage()

  def _reset_rollout_storage(self):
    self._obs = []
    self._actions = []
    self._rewards = []
    self._values = []
    self._dones = []

  def _obs_tensor(self, obs):
    return torch.tensor([list(obs)], dtype=torch.float32)

  def _action_tuple(self, raw):
    a = raw.squeeze(0).detach()
    return (float(a[0].item()), float(a[1].item()))

  def act(self, obs):
    """学習時: ガウスから (knee, ankle) をサンプル。返り値は ((knee, ankle), value)。"""
    o = self._obs_tensor(obs)
    mean, std = self.actor(o)
    dist = torch.distributions.Normal(mean, std)
    raw = dist.rsample()
    value = self.critic(o)
    return self._action_tuple(raw), value.squeeze(0)

  def act_eval(self, obs):
    """評価用: 平均のみ（ノイズなし）。"""
    self.actor.eval()
    self.critic.eval()
    with torch.no_grad():
      o = self._obs_tensor(obs)
      mean, _ = self.actor(o)
      action = self._action_tuple(mean)
    self.actor.train()
    self.critic.train()
    return action

  def store(self, obs, action, reward, value, done):
    self._obs.append(obs)
    self._actions.append(action)
    self._rewards.append(float(reward))
    self._values.append(value.detach())
    self._dones.append(float(done))

  def update(self, last_obs):
    with torch.no_grad():
      last_v = self.critic(self._obs_tensor(last_obs)).squeeze(0)

    obs_list = self._obs
    T = len(obs_list)
    if T == 0:
      self._reset_rollout_storage()
      return {
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "entropy": 0.0,
        "mean_target": 0.0,
      }

    rewards = torch.tensor(self._rewards, dtype=torch.float32)
    values = torch.stack(self._values).squeeze(-1)
    dones = torch.tensor(self._dones, dtype=torch.float32)

    vals_next = torch.cat([values[1:], last_v.view(1)], dim=0)
    targets = rewards + GAMMA * vals_next * (1.0 - dones)
    advantages = targets - values

    adv = advantages
    adv = (adv - adv.mean()) / (adv.std() + 1e-8)

    obs_batch = torch.tensor([list(o) for o in obs_list], dtype=torch.float32)
    actions_batch = torch.tensor(self._actions, dtype=torch.float32)

    total_policy_loss = 0.0
    total_value_loss = 0.0
    total_entropy = 0.0
    n_mb = 0

    idx = np.arange(T)
    np.random.shuffle(idx)

    for start in range(0, T, MINIBATCH_SIZE):
      mb = idx[start : start + MINIBATCH_SIZE]
      mb_obs = obs_batch[mb]
      mb_actions = actions_batch[mb]
      mb_adv = adv[mb].detach()
      mb_targets = targets[mb].detach()

      mean, std = self.actor(mb_obs)
      dist = torch.distributions.Normal(mean, std)
      log_probs = dist.log_prob(mb_actions).sum(dim=-1)

      policy_loss = -(log_probs * mb_adv).mean()

      new_values = self.critic(mb_obs)
      value_loss = nn.functional.mse_loss(new_values, mb_targets)

      entropy = dist.entropy().sum(dim=-1).mean()

      loss = policy_loss + VALUE_COEF * value_loss - ENTROPY_COEF * entropy

      self.optimizer.zero_grad()
      loss.backward()
      nn.utils.clip_grad_norm_(
        list(self.actor.parameters()) + list(self.critic.parameters()),
        MAX_GRAD_NORM,
      )
      self.optimizer.step()

      total_policy_loss += policy_loss.item()
      total_value_loss += value_loss.item()
      total_entropy += entropy.item()
      n_mb += 1

    self._reset_rollout_storage()

    return {
      "policy_loss": total_policy_loss / max(n_mb, 1),
      "value_loss": total_value_loss / max(n_mb, 1),
      "entropy": total_entropy / max(n_mb, 1),
      "mean_target": targets.mean().item(),
    }
