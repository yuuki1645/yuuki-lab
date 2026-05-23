"""exp_005: 2 関節脚 PPO（squashed Gaussian 方策）。

方策は Normal → tanh で [-1, 1]²（膝・足首サーボ目標）。
1 update = ROLLOUT_STEPS 分を収集し、GAE(λ) で advantage を計算したあと
PPO clipped surrogate を PPO_EPOCHS 回（ミニバッチ）適用する。
収集時の log_prob を保存し、方策比 r = exp(log π_new - log π_old) を clip する。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal, TransformedDistribution
from torch.distributions.transforms import TanhTransform

from . import config


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


def _compute_gae(
  rewards: torch.Tensor,
  values: torch.Tensor,
  dones: torch.Tensor,
  last_v: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
  """GAE(λ) で advantage と return（価値ターゲット）を計算する。"""
  t_len = rewards.shape[0]
  advantages = torch.zeros(t_len, dtype=torch.float32)
  last_gae = 0.0
  for t in reversed(range(t_len)):
    if t == t_len - 1:
      next_v = last_v
    else:
      next_v = values[t + 1]
    non_terminal = 1.0 - dones[t]
    delta = rewards[t] + config.GAMMA * next_v * non_terminal - values[t]
    last_gae = float(
      delta + config.GAMMA * config.GAE_LAMBDA * non_terminal * last_gae
    )
    advantages[t] = last_gae
  returns = advantages + values
  return advantages, returns


class AgentPPO:
  """on-policy PPO（clipped surrogate + GAE）。"""

  def __init__(self, obs_dim: int = config.OBS_DIM, action_dim: int = config.ACTION_DIM):
    self.obs_dim = obs_dim
    self.action_dim = action_dim
    print(
      f"[PPO {config.EXP_NAME}] obs_dim={self.obs_dim}, "
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
    self._log_probs = []

  def _obs_tensor(self, obs):
    return torch.tensor([list(obs)], dtype=torch.float32)

  @staticmethod
  def _action_tuple(action_tensor: torch.Tensor) -> tuple[float, float]:
    a = action_tensor.detach().squeeze(0)
    return float(a[0].item()), float(a[1].item())

  @staticmethod
  def _squashed_log_prob(dist, action: torch.Tensor) -> torch.Tensor:
    return dist.log_prob(action).sum(dim=-1).clamp(
      -config.LOG_PROB_CLIP,
      config.LOG_PROB_CLIP,
    )

  def value_at(self, obs):
    """現在の Critic による V(s)（推論・デバッグ用）。"""
    o = self._obs_tensor(obs)
    return self.critic(o).squeeze(0)

  def act(self, obs):
    """学習用: 確率的に行動をサンプルし、V(s) と収集時 log π(a|s) を返す。"""
    o = self._obs_tensor(obs)
    dist = self.actor.squashed_dist(o)
    action = dist.rsample()
    log_prob = self._squashed_log_prob(dist, action)
    value = self.critic(o)
    return self._action_tuple(action), value.squeeze(0), log_prob.squeeze(0).detach()

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

  def store(self, obs, action, reward, value, done, log_prob):
    """ロールアウト 1 ステップ分をバッファへ追加（update 後にクリア）。"""
    self._obs.append(obs)
    self._actions.append(action)
    self._rewards.append(float(reward))
    self._values.append(value.detach())
    self._dones.append(float(done))
    self._log_probs.append(log_prob.detach())

  def update(self, last_obs):
    """ロールアウトバッファを消費して PPO 更新を行う。

    last_obs: ロールアウト末尾の次状態（ブートストラップ V(s_{T+1}) 用）。
    """
    with torch.no_grad():
      last_v = self.critic(self._obs_tensor(last_obs)).squeeze(0)

    obs_list = self._obs
    t_len = len(obs_list)
    if t_len == 0:
      self._reset_rollout_storage()
      return self._empty_stats()

    rewards = torch.tensor(self._rewards, dtype=torch.float32).clamp(
      -config.REWARD_CLIP,
      config.REWARD_CLIP,
    )
    values = torch.stack(self._values).squeeze(-1)
    dones = torch.tensor(self._dones, dtype=torch.float32)
    old_log_probs = torch.stack(self._log_probs).squeeze(-1)

    advantages, returns = _compute_gae(rewards, values, dones, last_v)
    adv_std = max(float(advantages.std().item()), config.ADV_STD_MIN)
    adv = (advantages - advantages.mean()) / adv_std
    adv = adv.clamp(-config.ADV_CLIP, config.ADV_CLIP)

    obs_batch = torch.tensor([list(o) for o in obs_list], dtype=torch.float32)
    actions_batch = torch.tensor(self._actions, dtype=torch.float32)
    mb_actions = actions_batch.clamp(
      -1.0 + config.ACTION_LOG_PROB_EPS,
      1.0 - config.ACTION_LOG_PROB_EPS,
    )

    with torch.no_grad():
      probe_loc, _ = self.actor(obs_batch[: min(8, t_len)])
      if not torch.isfinite(probe_loc).all():
        print("[PPO] actor output is non-finite; skipping this update")
        self._reset_rollout_storage()
        return self._empty_stats()

    total_policy_loss = 0.0
    total_value_loss = 0.0
    total_entropy = 0.0
    total_approx_kl = 0.0
    total_clip_fraction = 0.0
    n_mb = 0

    for _epoch in range(config.PPO_EPOCHS):
      idx = np.arange(t_len)
      np.random.shuffle(idx)
      epoch_kl = 0.0
      epoch_mb = 0

      for start in range(0, t_len, config.MINIBATCH_SIZE):
        mb = idx[start : start + config.MINIBATCH_SIZE]
        mb_obs = obs_batch[mb]
        if not torch.isfinite(mb_obs).all():
          continue

        mb_adv = adv[mb].detach()
        mb_returns = returns[mb].detach()
        mb_old_log_probs = old_log_probs[mb].detach()
        mb_actions_sel = mb_actions[mb]

        dist = self.actor.squashed_dist(mb_obs)
        new_log_probs = self._squashed_log_prob(dist, mb_actions_sel)
        if not torch.isfinite(new_log_probs).all():
          continue

        ratio = torch.exp(new_log_probs - mb_old_log_probs)
        surr1 = ratio * mb_adv
        surr2 = (
          torch.clamp(ratio, 1.0 - config.CLIP_EPS, 1.0 + config.CLIP_EPS) * mb_adv
        )
        policy_loss = -torch.min(surr1, surr2).mean()

        new_values = self.critic(mb_obs)
        value_loss = nn.functional.mse_loss(new_values, mb_returns)

        loc, std = self.actor(mb_obs)
        entropy = self.actor.gaussian_entropy(loc, std)

        loss = (
          policy_loss
          + config.VALUE_COEF * value_loss
          - config.ENTROPY_COEF * entropy
        )
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

        with torch.no_grad():
          approx_kl = (mb_old_log_probs - new_log_probs).mean().item()
          clip_fraction = (
            (torch.abs(ratio - 1.0) > config.CLIP_EPS).float().mean().item()
          )

        total_policy_loss += policy_loss.item()
        total_value_loss += value_loss.item()
        total_entropy += entropy.item()
        total_approx_kl += approx_kl
        total_clip_fraction += clip_fraction
        epoch_kl += approx_kl
        n_mb += 1
        epoch_mb += 1

      if (
        config.TARGET_KL > 0.0
        and epoch_mb > 0
        and (epoch_kl / epoch_mb) > config.TARGET_KL
      ):
        break

    self._reset_rollout_storage()

    denom = max(n_mb, 1)
    return {
      "policy_loss": total_policy_loss / denom,
      "value_loss": total_value_loss / denom,
      "entropy": total_entropy / denom,
      "mean_target": returns.mean().item(),
      "approx_kl": total_approx_kl / denom,
      "clip_fraction": total_clip_fraction / denom,
    }

  @staticmethod
  def _empty_stats() -> dict[str, float]:
    return {
      "policy_loss": 0.0,
      "value_loss": 0.0,
      "entropy": 0.0,
      "mean_target": float("nan"),
      "approx_kl": float("nan"),
      "clip_fraction": float("nan"),
    }

  @classmethod
  def from_checkpoint(
    cls,
    path: str | Path,
    *,
    lr: float | None = None,
    load_optimizer: bool = True,
    map_location: str | torch.device = "cpu",
  ) -> AgentPPO:
    """保存済みチェックポイントからエージェントを復元する。"""
    from . import checkpoint

    payload = checkpoint.load_checkpoint(path, map_location=map_location)
    fmt = payload.get("format", "")
    if fmt and fmt != checkpoint.EXPECTED_CHECKPOINT_FORMAT:
      raise ValueError(
        f"checkpoint format {fmt!r} != expected {checkpoint.EXPECTED_CHECKPOINT_FORMAT!r}"
      )
    obs_dim = int(payload["obs_dim"])
    action_dim = int(payload["action_dim"])
    if obs_dim != config.OBS_DIM:
      raise ValueError(
        f"checkpoint obs_dim={obs_dim} does not match config.OBS_DIM={config.OBS_DIM}"
      )
    agent = cls(obs_dim=obs_dim, action_dim=action_dim)
    agent.actor.load_state_dict(payload["actor"])
    agent.critic.load_state_dict(payload["critic"])
    if lr is not None:
      agent.set_learning_rate(lr)
    elif load_optimizer and "optimizer" in payload:
      agent.optimizer.load_state_dict(payload["optimizer"])
    return agent


# train / visualize 用のエイリアス
OBS_DIM = config.OBS_DIM
ROLLOUT_STEPS = config.ROLLOUT_STEPS
