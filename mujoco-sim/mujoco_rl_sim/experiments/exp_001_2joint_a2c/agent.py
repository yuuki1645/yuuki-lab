"""exp_001: 2 関節脚 A2C（squashed Gaussian 方策）。"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal, TransformedDistribution
from torch.distributions.transforms import TanhTransform

from mujoco_rl_sim.experiments.exp_001_2joint_a2c import config


class Actor(nn.Module):
  """観測 -> ガウス（事前）-> tanh で [-1, 1]。"""

  def __init__(self, obs_dim: int, action_dim: int):
    super().__init__()
    self.action_dim = action_dim
    self.net = nn.Sequential(
      nn.Linear(obs_dim, 64),
      nn.ReLU(),
      nn.Linear(64, 64),
      nn.ReLU(),
      nn.Linear(64, action_dim),
    )
    self.log_std = nn.Parameter(torch.zeros(action_dim))

  def forward(self, obs):
    loc = self.net(obs)
    std = self.log_std.exp().expand_as(loc).clamp(min=1e-6)
    return loc, std

  def squashed_dist(self, obs):
    loc, std = self.forward(obs)
    base = Normal(loc, std)
    return TransformedDistribution(base, TanhTransform())

  @staticmethod
  def squashed_entropy(loc: torch.Tensor, std: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
    base_entropy = Normal(loc, std).entropy().sum(dim=-1)
    jacobian = torch.log(1 - actions.pow(2) + 1e-6).sum(dim=-1)
    return base_entropy + jacobian


class Critic(nn.Module):
  def __init__(self, obs_dim: int):
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


class AgentExp001A2C:
  def __init__(self, obs_dim: int = config.OBS_DIM, action_dim: int = config.ACTION_DIM):
    self.obs_dim = obs_dim
    self.action_dim = action_dim
    print(f"[A2C exp_001] obs_dim={self.obs_dim}, action_dim={self.action_dim} (continuous)")

    self.actor = Actor(obs_dim, action_dim)
    self.critic = Critic(obs_dim)
    self.optimizer = optim.Adam(
      list(self.actor.parameters()) + list(self.critic.parameters()),
      lr=config.LR,
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

  @staticmethod
  def _action_tuple(action_tensor: torch.Tensor) -> tuple[float, float]:
    a = action_tensor.detach().squeeze(0)
    return float(a[0].item()), float(a[1].item())

  def act(self, obs):
    o = self._obs_tensor(obs)
    dist = self.actor.squashed_dist(o)
    action = dist.rsample()
    value = self.critic(o)
    return self._action_tuple(action), value.squeeze(0)

  def act_eval(self, obs):
    self.actor.eval()
    self.critic.eval()
    with torch.no_grad():
      o = self._obs_tensor(obs)
      loc, _ = self.actor(o)
      action = torch.tanh(loc)
    self.actor.train()
    self.critic.train()
    return self._action_tuple(action)

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
    t_len = len(obs_list)
    if t_len == 0:
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
    targets = rewards + config.GAMMA * vals_next * (1.0 - dones)
    advantages = targets - values
    adv = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    obs_batch = torch.tensor([list(o) for o in obs_list], dtype=torch.float32)
    actions_batch = torch.tensor(self._actions, dtype=torch.float32)

    total_policy_loss = 0.0
    total_value_loss = 0.0
    total_entropy = 0.0
    n_mb = 0

    idx = np.arange(t_len)
    np.random.shuffle(idx)

    for start in range(0, t_len, config.MINIBATCH_SIZE):
      mb = idx[start : start + config.MINIBATCH_SIZE]
      mb_obs = obs_batch[mb]
      mb_actions = actions_batch[mb]
      mb_adv = adv[mb].detach()
      mb_targets = targets[mb].detach()

      dist = self.actor.squashed_dist(mb_obs)
      log_probs = dist.log_prob(mb_actions).sum(dim=-1)
      policy_loss = -(log_probs * mb_adv).mean()

      new_values = self.critic(mb_obs)
      value_loss = nn.functional.mse_loss(new_values, mb_targets)

      loc, std = self.actor(mb_obs)
      entropy = self.actor.squashed_entropy(loc, std, mb_actions).mean()

      loss = policy_loss + config.VALUE_COEF * value_loss - config.ENTROPY_COEF * entropy

      self.optimizer.zero_grad()
      loss.backward()
      nn.utils.clip_grad_norm_(
        list(self.actor.parameters()) + list(self.critic.parameters()),
        config.MAX_GRAD_NORM,
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


Agent010A2C = AgentExp001A2C
OBS_DIM = config.OBS_DIM
ROLLOUT_STEPS = config.ROLLOUT_STEPS
