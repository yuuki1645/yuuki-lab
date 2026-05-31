"""exp_003: 2 関節脚 A2C（squashed Gaussian 方策）。

方策は Normal → tanh で [-1, 1]²（膝・足首サーボ目標）。
1 update = ROLLOUT_STEPS 分を store し、GAE 風の advantage 正規化後にミニバッチで勾配更新。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal, TransformedDistribution
from torch.distributions.transforms import TanhTransform

import config


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
    self.log_std = nn.Parameter(torch.full((action_dim,), -1.0))

  def forward(self, obs):
    loc = self.net(obs)
    std = self.log_std.exp().expand_as(loc).clamp(min=config.STD_MIN)
    return loc, std

  def squashed_dist(self, obs):
    loc, std = self.forward(obs)
    base = Normal(loc, std)
    return TransformedDistribution(base, TanhTransform())

  @staticmethod
  def gaussian_entropy(loc: torch.Tensor, std: torch.Tensor) -> torch.Tensor:
    """Tanh 変換前の Normal のエントロピー（TransformedDistribution.entropy は未実装）。"""
    return Normal(loc, std).entropy().sum(dim=-1).mean()


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


class AgentA2C:
  """on-policy A2C。Actor-Critic を同一 Adam で更新する。"""

  def __init__(self, obs_dim: int = config.OBS_DIM, action_dim: int = config.ACTION_DIM):
    self.obs_dim = obs_dim
    self.action_dim = action_dim
    print(
      f"[A2C {config.EXP_NAME}] obs_dim={self.obs_dim}, "
      f"action_dim={self.action_dim} (continuous)"
    )

    self.actor = Actor(obs_dim, action_dim)
    self.critic = Critic(obs_dim)
    self.optimizer = optim.Adam(
      list(self.actor.parameters()) + list(self.critic.parameters()),
      lr=config.LR,
    )
    self._reset_rollout_storage()

  def set_learning_rate(self, lr: float) -> None:
    """全 param_group の学習率を更新する（再開時の微調整用）。"""
    for group in self.optimizer.param_groups:
      group["lr"] = float(lr)

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

  def value_at(self, obs):
    """現在の Critic による V(s)（推論・デバッグ用）。"""
    o = self._obs_tensor(obs)
    return self.critic(o).squeeze(0)

  def act(self, obs):
    """学習用: 確率的に行動をサンプルし、同時に V(s) を返す。"""
    o = self._obs_tensor(obs)
    dist = self.actor.squashed_dist(o)
    action = dist.rsample()
    value = self.critic(o)
    return self._action_tuple(action), value.squeeze(0)

  def act_eval(self, obs):
    """評価用: 平均行動 tanh(loc)（ノイズなし）。"""
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
    """ロールアウト 1 ステップ分をバッファへ追加（update 後にクリア）。"""
    self._obs.append(obs)
    self._actions.append(action)
    self._rewards.append(float(reward))
    self._values.append(value.detach())
    self._dones.append(float(done))

  def update(self, last_obs):
    """ロールアウトバッファを消費して 1 回分の方策・価値更新を行う。

    last_obs: ロールアウト末尾の次状態（ブートストラップ V(s_{T+1}) 用）。
    """
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

    rewards = torch.tensor(self._rewards, dtype=torch.float32).clamp(
      -config.REWARD_CLIP,
      config.REWARD_CLIP,
    )
    values = torch.stack(self._values).squeeze(-1)
    dones = torch.tensor(self._dones, dtype=torch.float32)

    # 1 ステップ TD ターゲット（done=1 の次価値は打ち切り）
    vals_next = torch.cat([values[1:], last_v.view(1)], dim=0)
    targets = rewards + config.GAMMA * vals_next * (1.0 - dones)
    advantages = targets - values
    adv_std = max(float(advantages.std().item()), config.ADV_STD_MIN)
    adv = (advantages - advantages.mean()) / adv_std
    adv = adv.clamp(-config.ADV_CLIP, config.ADV_CLIP)

    obs_batch = torch.tensor([list(o) for o in obs_list], dtype=torch.float32)
    actions_batch = torch.tensor(self._actions, dtype=torch.float32)

    with torch.no_grad():
      probe_loc, _ = self.actor(obs_batch[: min(8, t_len)])
      if not torch.isfinite(probe_loc).all():
        print("[A2C] actor output is non-finite; skipping this update")
        self._reset_rollout_storage()
        return {
          "policy_loss": float("nan"),
          "value_loss": float("nan"),
          "entropy": float("nan"),
          "mean_target": float("nan"),
        }

    total_policy_loss = 0.0
    total_value_loss = 0.0
    total_entropy = 0.0
    n_mb = 0

    idx = np.arange(t_len)
    np.random.shuffle(idx)

    for start in range(0, t_len, config.MINIBATCH_SIZE):
      mb = idx[start : start + config.MINIBATCH_SIZE]
      mb_obs = obs_batch[mb]
      if not torch.isfinite(mb_obs).all():
        continue
      # tanh の端で log_prob が発散するのを避ける
      mb_actions = actions_batch[mb].clamp(
        -1.0 + config.ACTION_LOG_PROB_EPS,
        1.0 - config.ACTION_LOG_PROB_EPS,
      )
      mb_adv = adv[mb].detach()
      mb_targets = targets[mb].detach()

      dist = self.actor.squashed_dist(mb_obs)
      log_probs = dist.log_prob(mb_actions).sum(dim=-1).clamp(
        -config.LOG_PROB_CLIP,
        config.LOG_PROB_CLIP,
      )
      if not torch.isfinite(log_probs).all():
        continue
      policy_loss = -(log_probs * mb_adv).mean()

      new_values = self.critic(mb_obs)
      value_loss = nn.functional.mse_loss(new_values, mb_targets)

      loc, std = self.actor(mb_obs)
      entropy = self.actor.gaussian_entropy(loc, std)

      loss = policy_loss + config.VALUE_COEF * value_loss - config.ENTROPY_COEF * entropy
      if not torch.isfinite(loss):
        continue

      self.optimizer.zero_grad()
      loss.backward()
      nn.utils.clip_grad_norm_(
        list(self.actor.parameters()) + list(self.critic.parameters()),
        config.MAX_GRAD_NORM,
      )
      if not all(
        torch.isfinite(p.grad).all()
        for p in list(self.actor.parameters()) + list(self.critic.parameters())
        if p.grad is not None
      ):
        self.optimizer.zero_grad()
        continue
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

  @classmethod
  def from_checkpoint(
    cls,
    path: str | Path,
    *,
    lr: float | None = None,
    load_optimizer: bool = True,
    map_location: str | torch.device = "cpu",
  ) -> AgentA2C:
    """保存済みチェックポイントからエージェントを復元する。

    lr を指定した場合は optimizer を読み込まず、新しい学習率だけを設定する。
    """
    from . import checkpoint

    payload = checkpoint.load_checkpoint(path, map_location=map_location)
    obs_dim = int(payload["obs_dim"])
    action_dim = int(payload["action_dim"])
    if obs_dim != config.OBS_DIM:
      raise ValueError(
        f"checkpoint obs_dim={obs_dim} does not match config.OBS_DIM={config.OBS_DIM} "
        f"(e.g. rel_imu_x removed: retrain or use a matching checkpoint)"
      )
    agent = cls(obs_dim=obs_dim, action_dim=action_dim)
    agent.actor.load_state_dict(payload["actor"])
    agent.critic.load_state_dict(payload["critic"])
    if lr is not None:
      agent.set_learning_rate(lr)
    elif load_optimizer and "optimizer" in payload:
      agent.optimizer.load_state_dict(payload["optimizer"])
    return agent


# 旧実験名との互換
OBS_DIM = config.OBS_DIM
ROLLOUT_STEPS = config.ROLLOUT_STEPS
