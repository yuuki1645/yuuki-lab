import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim


GAMMA = 0.99
GAE_LAMBDA = 0.95
CLIP_EPS = 0.2
LR = 3e-4
ROLLOUT_STEPS = 512
UPDATE_EPOCHS = 8
MINIBATCH_SIZE = 64
VALUE_COEF = 0.5
ENTROPY_COEF = 0.01
MAX_GRAD_NORM = 0.5


class Actor(nn.Module):
  """観測から1次元ガウス方策の平均を出す（標準偏差はグローバル学習パラメータ）。"""

  def __init__(self, obs_dim):
    super().__init__()
    self.net = nn.Sequential(
      nn.Linear(obs_dim, 32),
      nn.ReLU(),
      nn.Linear(32, 32),
      nn.ReLU(),
      nn.Linear(32, 1),
      nn.Tanh(),
    )
    self.log_std = nn.Parameter(torch.zeros(1))

  def forward(self, obs):
    mean = self.net(obs)
    std = self.log_std.exp().expand_as(mean).clamp(min=1e-6)
    return mean, std


class Critic(nn.Module):
  def __init__(self, obs_dim):
    super().__init__()
    self.net = nn.Sequential(
      nn.Linear(obs_dim, 32),
      nn.ReLU(),
      nn.Linear(32, 32),
      nn.ReLU(),
      nn.Linear(32, 1),
    )

  def forward(self, obs):
    return self.net(obs).squeeze(-1)


class Agent007PPO:
  def __init__(self, obs_dim):
    self.obs_dim = obs_dim
    print(f"obs_dim: {self.obs_dim}, action_dim: 1 (continuous)")

    self.actor = Actor(obs_dim)
    self.critic = Critic(obs_dim)

    self.optimizer = optim.Adam(
      list(self.actor.parameters()) + list(self.critic.parameters()),
      lr=LR,
    )

    self._reset_rollout_storage()

  def _reset_rollout_storage(self):
    self._obs = []
    self._actions = []
    self._log_probs = []
    self._rewards = []
    self._values = []
    self._dones = []

  def _obs_tensor(self, obs):
    x, pitch, prev_action = obs
    return torch.tensor([[float(x), float(pitch), float(prev_action)]], dtype=torch.float32)

  def act(self, obs):
    """行動選択（学習時はサンプル）。返り値: action(float), log_prob(tensor), value(tensor)"""
    o = self._obs_tensor(obs)
    mean, std = self.actor(o)
    dist = torch.distributions.Normal(mean, std)
    raw = dist.rsample()
    log_prob = dist.log_prob(raw).sum(dim=-1)
    value = self.critic(o)
    action = raw.squeeze(0).squeeze(-1).detach().item()
    return action, log_prob.squeeze(0), value.squeeze(0)

  def act_eval(self, obs):
    """評価用: 平均のみ（ノイズなし）。"""
    self.actor.eval()
    self.critic.eval()
    with torch.no_grad():
      o = self._obs_tensor(obs)
      mean, _ = self.actor(o)
      action = mean.squeeze().item()
    self.actor.train()
    self.critic.train()
    return action

  def store(self, obs, action, reward, log_prob, value, done):
    self._obs.append(obs)
    self._actions.append(action)
    self._rewards.append(float(reward))
    self._log_probs.append(log_prob.detach())
    self._values.append(value.detach())
    self._dones.append(float(done))

  def update(self, last_obs):
    """ロールアウト終端の観測 last_obs でブートストラップしてGAE計算→PPO更新。"""
    with torch.no_grad():
      last_v = self.critic(self._obs_tensor(last_obs)).squeeze(0)

    obs_list = self._obs
    T = len(obs_list)
    rewards = torch.tensor(self._rewards, dtype=torch.float32)
    values = torch.stack(self._values)
    dones = torch.tensor(self._dones, dtype=torch.float32)

    advantages = torch.zeros(T, dtype=torch.float32)
    last_gae = 0.0
    for t in reversed(range(T)):
      if t == T - 1:
        next_non_terminal = 1.0 - dones[t]
        next_value = last_v
      else:
        next_non_terminal = 1.0 - dones[t]
        next_value = values[t + 1]
      delta = rewards[t] + GAMMA * next_value * next_non_terminal - values[t]
      last_gae = delta + GAMMA * GAE_LAMBDA * next_non_terminal * last_gae
      advantages[t] = last_gae

    returns = advantages + values

    adv = advantages
    adv = (adv - adv.mean()) / (adv.std() + 1e-8)

    obs_batch = torch.tensor(
      [[float(o[0]), float(o[1]), float(o[2])] for o in obs_list],
      dtype=torch.float32,
    )
    actions_batch = torch.tensor(self._actions, dtype=torch.float32).unsqueeze(-1)
    old_log_probs = torch.stack(self._log_probs)

    total_policy_loss = 0.0
    total_value_loss = 0.0
    total_entropy = 0.0
    updates = 0

    idx = np.arange(T)
    for _ in range(UPDATE_EPOCHS):
      np.random.shuffle(idx)
      for start in range(0, T, MINIBATCH_SIZE):
        mb = idx[start:start + MINIBATCH_SIZE]
        mb_obs = obs_batch[mb]
        mb_actions = actions_batch[mb]
        mb_old_log = old_log_probs[mb]
        mb_adv = adv[mb]
        mb_ret = returns[mb]

        mean, std = self.actor(mb_obs)
        dist = torch.distributions.Normal(mean, std)
        new_log = dist.log_prob(mb_actions).sum(dim=-1)

        ratio = torch.exp(new_log - mb_old_log)
        surr1 = ratio * mb_adv
        surr2 = torch.clamp(ratio, 1.0 - CLIP_EPS, 1.0 + CLIP_EPS) * mb_adv
        policy_loss = -torch.min(surr1, surr2).mean()

        new_values = self.critic(mb_obs)
        value_loss = nn.functional.mse_loss(new_values, mb_ret)

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
        updates += 1

    self._reset_rollout_storage()

    return {
      "policy_loss": total_policy_loss / max(updates, 1),
      "value_loss": total_value_loss / max(updates, 1),
      "entropy": total_entropy / max(updates, 1),
      "mean_return": returns.mean().item(),
    }
