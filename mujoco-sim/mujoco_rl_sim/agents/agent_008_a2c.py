"""008: Advantage Actor-Critic (A2C) — PPO 版と同じ Actor/Critic 形、更新だけシンプルに。

PPO との違い（このファイル）:
  - 確率比のクリップなし（方策は普通の方策勾配で更新）。
  - ロールアウト1回につき、ミニバッチに分けて数回更新するのではなく、
    まとめた損失を1回（複数ミニバッチに分割しても合計1エポック）で逆伝播。
  - アドバンテージは GAE ではなく、1ステップ先まで見た TD 目標との差（TD(0) 型）。

※ 論文でいう「複数環境を並列に回す A2C」はせず、train スクリプトは PPO と同様に
   環境1本・直列ロールアウト（分かりやすさ優先）。
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim


GAMMA = 0.99
LR = 3e-4
ROLLOUT_STEPS = 512
# ROLLOUT_STEPS = 15
VALUE_COEF = 0.5
ENTROPY_COEF = 0.01
MAX_GRAD_NORM = 0.5
# ロールアウトが長いとき用（A2C では PPO ほど何度も同じデータを使い回さない想定）
MINIBATCH_SIZE = 256


class Actor(nn.Module):
  """観測 -> ガウス方策の平均。標準偏差は状態によらない1スカラーを学習（007 PPO と同型）。"""

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
  """観測 -> 状態価値 V(s) のスカラー。"""

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


class Agent008A2C:
  def __init__(self, obs_dim):
    self.obs_dim = obs_dim
    print(f"[A2C] obs_dim={self.obs_dim}, action_dim=1 (continuous)")

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
    self._rewards = []
    self._values = []
    self._dones = []

  def _obs_tensor(self, obs):
    x, pitch, prev_action = obs
    return torch.tensor([[float(x), float(pitch), float(prev_action)]], dtype=torch.float32)

  def act(self, obs):
    """学習時: ガウスから行動をサンプル。返り値は (action, value)。"""
    o = self._obs_tensor(obs)
    mean, std = self.actor(o)
    # print(f"mean: {mean} | std: {std}")
    dist = torch.distributions.Normal(mean, std)
    raw = dist.rsample()
    value = self.critic(o)
    action = raw.squeeze(0).squeeze(-1).detach().item()
    return action, value.squeeze(0)

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

  def store(self, obs, action, reward, value, done):
    """1ステップ分をロールアウト用バッファに追加。"""
    self._obs.append(obs)
    self._actions.append(action)
    self._rewards.append(float(reward))
    self._values.append(value.detach())
    self._dones.append(float(done))

    # print(f"obs: ({obs[0]:7.3f}, {obs[1]:7.3f}, {obs[2]:7.3f}) | action: {action:7.3f} | reward: {reward:7.3f} | value: {value:7.3f} | done: {done}")

  def update(self, last_obs):
    """ロールアウト全体で損失を計算し、勾配1セット分で更新する。

    last_obs:
      ロールアウト直後の観測 s_T。TD 目標の「次の価値」に V(s_T) を使う。
    """
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

    # V(s_{t+1}): 最後のステップだけはロールアウト外の last_obs からブートストラップ
    vals_next = torch.cat([values[1:], last_v.view(1)], dim=0)

    # TD(0) の1ステップ目標: y_t = r_t + gamma * V(s_{t+1}) * (エピソード継続なら1)
    targets = rewards + GAMMA * vals_next * (1.0 - dones)

    # アドバンテージ = 「目標」と「いまの V の予測」の差（方策更新の重み）
    advantages = targets - values

    adv = advantages
    adv = (adv - adv.mean()) / (adv.std() + 1e-8)

    obs_batch = torch.tensor(
      [[float(o[0]), float(o[1]), float(o[2])] for o in obs_list],
      dtype=torch.float32,
    )
    actions_batch = torch.tensor(self._actions, dtype=torch.float32).unsqueeze(-1)
    # print(f"actions_batch: {actions_batch}")

    total_policy_loss = 0.0
    total_value_loss = 0.0
    total_entropy = 0.0
    n_mb = 0

    idx = np.arange(T)
    np.random.shuffle(idx)

    # メモリ節約と安定のためミニバッチに分割（各ミニバッチで backward し、最後に step しない方が
    # 勾配が累積されるので、ここでは各ミニバッチごとに step する = 複数ステップの勾配降下）
    for start in range(0, T, MINIBATCH_SIZE):
      mb = idx[start : start + MINIBATCH_SIZE]
      mb_obs = obs_batch[mb]
      mb_actions = actions_batch[mb]
      mb_adv = adv[mb].detach()
      mb_targets = targets[mb].detach()

      mean, std = self.actor(mb_obs)
      dist = torch.distributions.Normal(mean, std)
      log_probs = dist.log_prob(mb_actions).sum(dim=-1)

      # 方策損失: 良い行動ほど log pi を大きく（advantage が正なら）
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
