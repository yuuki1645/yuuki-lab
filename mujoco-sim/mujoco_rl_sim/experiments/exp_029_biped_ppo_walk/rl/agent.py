"""exp_029: 両脚交互片脚歩行 12 DOF PPO（squashed Gaussian 方策・拡大 MLP）。

【PPO とは（このファイルの前提）】
  方策（どう動くか）を、環境で集めたデータで少しずつ改善する強化学習。
  普通の方策勾配法は「1 回データを集めたら 1 回だけ更新」だが、
  PPO は同じデータを何度か使いながら、**方策を急に大きく変えない**よう
  クリップ（上限・下限）で更新幅を制限する。performance collapse の抑制に使われることが多い。

【1 回の update の流れ（train.py から見た順）】
  1. act / store … ROLLOUT_STEPS 分、環境を回してバッファに保存
       （このときの log π_old(a|s) を必ず保存するのが PPO の要点）
  2. update … GAE で「どの行動が良かったか」(advantage) を計算
  3. update … 同じバッファを PPO_EPOCHS 回、ミニバッチで学習
       方策比 r = π_new / π_old を CLIP_EPS の範囲に収める

方策は Normal → tanh で [-1, 1]^action_dim（全サーボ目標）。
隠れ層は config.POLICY_HIDDEN_SIZES（既定 256→256→128）。
ハイパラは config.py（CLIP_EPS, PPO_EPOCHS, GAE_LAMBDA など）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal, TransformedDistribution
from torch.distributions.transforms import TanhTransform

from lib.experiment_context import ExperimentContext


def _build_mlp(
  in_dim: int,
  hidden_sizes: tuple[int, ...],
  out_dim: int,
) -> nn.Sequential:
  """ReLU MLP（最終層は線形・活性化なし）。"""
  layers: list[nn.Module] = []
  prev = in_dim
  for width in hidden_sizes:
    layers.append(nn.Linear(prev, width))
    layers.append(nn.ReLU())
    prev = width
  layers.append(nn.Linear(prev, out_dim))
  return nn.Sequential(*layers)


class Actor(nn.Module):
  """観測 -> ガウス（事前）-> tanh で [-1, 1]。"""

  def __init__(
    self,
    obs_dim: int,
    action_dim: int,
    *,
    hidden_sizes: tuple[int, ...],
    std_min: float,
  ):
    super().__init__()
    self.action_dim = action_dim
    self.hidden_sizes = hidden_sizes
    self.std_min = float(std_min)
    self.net = _build_mlp(obs_dim, hidden_sizes, action_dim)
    self.log_std = nn.Parameter(torch.full((action_dim,), -1.0))

  def forward(self, obs):
    loc = self.net(obs)
    std = self.log_std.exp().expand_as(loc).clamp(min=self.std_min)
    return loc, std

  def squashed_dist(self, obs):
    loc, std = self.forward(obs)
    base = Normal(loc, std)
    return TransformedDistribution(base, TanhTransform())

  @staticmethod
  def gaussian_entropy(loc: torch.Tensor, std: torch.Tensor) -> torch.Tensor:
    """Tanh 変換前の Normal のエントロピー（探索の大きさ。大きいほどランダム）。"""
    return Normal(loc, std).entropy().sum(dim=-1).mean()


class Critic(nn.Module):
  """状態価値 V(s): 「ここから先、どれくらい報酬が得られそうか」の予測。"""

  def __init__(
    self,
    obs_dim: int,
    *,
    hidden_sizes: tuple[int, ...],
  ):
    super().__init__()
    self.hidden_sizes = hidden_sizes
    self.net = _build_mlp(obs_dim, hidden_sizes, 1)

  def forward(self, obs):
    return self.net(obs).squeeze(-1)


def _compute_gae(
  rewards: torch.Tensor,
  values: torch.Tensor,
  dones: torch.Tensor,
  last_v: torch.Tensor,
  *,
  gamma: float,
  gae_lambda: float,
) -> tuple[torch.Tensor, torch.Tensor]:
  """GAE(λ): 各ステップの advantage（行動の良し悪し）と return（価値の教師信号）を求める。

  advantage が正 → その行動は平均より良かった（方策を強化したい方向）
  advantage が負 → 悪かった（弱化したい方向）

  TD 誤差 δ_t = r_t + γ V(s_{t+1}) - V(s_t) を、λ で平滑化して足し合わせる。
  λ=0 なら 1 ステップ先だけ、λ→1 なら長いリターンに近づく（config.GAE_LAMBDA=0.95）。

  returns = advantages + values … Critic の MSE ターゲット（価値関数を当てはめる用）
  """
  t_len = rewards.shape[0]
  advantages = torch.zeros(t_len, dtype=torch.float32)
  last_gae = 0.0
  for t in reversed(range(t_len)):
    if t == t_len - 1:
      # ロールアウト最後の次状態: まだエピソードが続くなら V(s_{T+1}) でブートストラップ
      next_v = last_v
    else:
      next_v = values[t + 1]
    # done=1 のときは次価値を使わない（転倒・終了で打ち切り）
    non_terminal = 1.0 - dones[t]
    delta = rewards[t] + float(gamma) * next_v * non_terminal - values[t]
    last_gae = float(
      delta + float(gamma) * float(gae_lambda) * non_terminal * last_gae
    )
    advantages[t] = last_gae
  returns = advantages + values
  return advantages, returns


class AgentPPO:
  """Proximal Policy Optimization（PPO）エージェント。

  exp_004 の A2C との主な違い:
    - データ収集時の log_prob を固定（π_old）し、更新後の log_prob（π_new）と比較
    - 方策損失に clip を入れ、1 ロールアウトあたりの方策変化を抑える
    - 同一ロールアウトを PPO_EPOCHS 回再利用（ミニバッチ学習）
  """

  def __init__(
    self,
    ctx: ExperimentContext,
  ):
    self._ctx = ctx
    sim_cfg = self._ctx.cfg.sim
    ppo_cfg = self._ctx.cfg.ppo
    obs_dim = int(sim_cfg.obs_dim)
    action_dim = int(sim_cfg.action_dim)
    hidden_sizes = tuple(int(x) for x in sim_cfg.policy_hidden_sizes)
    self.obs_dim = obs_dim
    self.action_dim = action_dim
    self.hidden_sizes = hidden_sizes
    print(
      f"[PPO {self._ctx.exp_name}] obs_dim={self.obs_dim}, "
      f"action_dim={self.action_dim}, "
      f"hidden={list(hidden_sizes)} (continuous)"
    )

    self.actor = Actor(
      obs_dim,
      action_dim,
      hidden_sizes=hidden_sizes,
      std_min=float(ppo_cfg.std_min),
    )
    self.critic = Critic(obs_dim, hidden_sizes=hidden_sizes)
    self.optimizer = optim.Adam(
      list(self.actor.parameters()) + list(self.critic.parameters()),
      lr=float(ppo_cfg.lr),
    )
    # CUDA が使えるときはバッチ推論に利用（Subproc VecEnv 向け）
    self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    self.actor.to(self._device)
    self.critic.to(self._device)
    # 1 ロールアウト分の一時バッファ（update の最後でクリア）
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
    # PPO 専用: 行動を取った瞬間の log π_old(a|s)。更新中は「古い方策」の確率として固定
    self._log_probs = []

  def _obs_tensor(self, obs):
    return torch.tensor([list(obs)], dtype=torch.float32, device=self._device)

  @staticmethod
  def _action_tuple(action_tensor: torch.Tensor) -> tuple[float, ...]:
    a = action_tensor.detach().reshape(-1)
    return tuple(float(x.item()) for x in a)

  def _squashed_log_prob(self, dist, action: torch.Tensor) -> torch.Tensor:
    """log π(a|s)。各次元の log_prob を足し合わせる。"""
    # tanh 変換後の log_prob は外れ値で暴れやすいので、安全域でクリップする。
    # しきい値は Hydra 側（ppo.log_prob_clip）で一元管理する。
    log_prob_clip = float(self._ctx.cfg.ppo.log_prob_clip)
    return dist.log_prob(action).sum(dim=-1).clamp(
      -log_prob_clip,
      log_prob_clip,
    )

  def value_at(self, obs):
    """現在の Critic による V(s)（推論・デバッグ用）。"""
    o = self._obs_tensor(obs)
    return self.critic(o).squeeze(0)

  def act(self, obs):
    """環境 Interaction 用: 確率的に行動を選び、V(s) と log π_old(a|s) を返す。

    log_prob は store 経由でバッファに入り、あとで update 内の「古い方策」として使う。
    detach しているので、収集フェーズの確率は更新で書き換わらない。
    """
    o = self._obs_tensor(obs)
    dist = self.actor.squashed_dist(o)
    action = dist.rsample()
    log_prob = self._squashed_log_prob(dist, action)
    value = self.critic(o)
    return (
      self._action_tuple(action.cpu()),
      value.squeeze(0).cpu(),
      log_prob.squeeze(0).detach().cpu(),
    )

  def act_batch(self, obs_batch: np.ndarray):
    """Subproc VecEnv 用: ``[N, obs_dim]`` をまとめて推論する。"""
    o = torch.as_tensor(obs_batch, dtype=torch.float32, device=self._device)
    dist = self.actor.squashed_dist(o)
    action = dist.rsample()
    log_prob = self._squashed_log_prob(dist, action)
    value = self.critic(o)
    return (
      action.detach().cpu().numpy(),
      value.detach().cpu().reshape(-1),
      log_prob.detach().cpu().reshape(-1),
    )

  def act_eval(self, obs):
    """評価・可視化用: 平均行動 tanh(loc)（ノイズなし）。"""
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
    """ロールアウト 1 ステップ分をバッファへ追加。update() 後にまとめてクリア。"""
    self._obs.append(obs)
    self._actions.append(action)
    self._rewards.append(float(reward))
    self._values.append(value.detach())
    self._dones.append(float(done))
    self._log_probs.append(log_prob.detach())

  def update(self, last_obs):
    """ロールアウト 1 本分の PPO 更新（train.py が ROLLOUT_STEPS ごとに 1 回呼ぶ）。

    last_obs: ロールアウト直後の観測（エピソード続行時の V(s') ブートストラップ用）
    """
    with torch.no_grad():
      last_v = self.critic(self._obs_tensor(last_obs)).squeeze(0)

    obs_list = self._obs
    t_len = len(obs_list)
    if t_len == 0:
      self._reset_rollout_storage()
      return self._empty_stats()

    # --- フェーズ A: テンソル化・GAE ---
    ppo_cfg = self._ctx.cfg.ppo
    rewards = torch.tensor(self._rewards, dtype=torch.float32).clamp(
      -float(ppo_cfg.reward_clip),
      float(ppo_cfg.reward_clip),
    )
    values = torch.stack(self._values).squeeze(-1)
    dones = torch.tensor(self._dones, dtype=torch.float32)
    # 収集時に保存した log π_old（この update 中は定数として扱う）
    old_log_probs = torch.stack(self._log_probs).squeeze(-1)

    advantages, returns = _compute_gae(
      rewards,
      values,
      dones,
      last_v,
      gamma=float(ppo_cfg.gamma),
      gae_lambda=float(ppo_cfg.gae_lambda),
    )
    # advantage を正規化すると学習が安定しやすい（平均 0・分散 ≈ 1）
    adv_std = max(float(advantages.std().item()), float(ppo_cfg.adv_std_min))
    adv = (advantages - advantages.mean()) / adv_std
    adv = adv.clamp(-float(ppo_cfg.adv_clip), float(ppo_cfg.adv_clip))

    obs_batch = torch.tensor(
      [list(o) for o in obs_list],
      dtype=torch.float32,
      device=self._device,
    )
    actions_batch = torch.tensor(
      self._actions,
      dtype=torch.float32,
      device=self._device,
    )
    # tanh の端 (+/-1) 付近では log_prob が発散しやすいので少し内側に寄せる
    mb_actions = actions_batch.clamp(
      -1.0 + float(ppo_cfg.action_log_prob_eps),
      1.0 - float(ppo_cfg.action_log_prob_eps),
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

    # --- フェーズ B: 同じロールアウトを PPO_EPOCHS 回学習（データ効率と clip のため）---
    for _epoch in range(int(ppo_cfg.ppo_epochs)):
      idx = np.arange(t_len)
      np.random.shuffle(idx)
      epoch_kl = 0.0
      epoch_mb = 0

      minibatch_size = int(ppo_cfg.minibatch_size)
      for start in range(0, t_len, minibatch_size):
        mb = idx[start : start + minibatch_size]
        mb_obs = obs_batch[mb]
        if not torch.isfinite(mb_obs).all():
          continue

        mb_adv = adv[mb].detach()
        mb_returns = returns[mb].detach()
        mb_old_log_probs = old_log_probs[mb].detach()
        mb_actions_sel = mb_actions[mb]

        # いまのネットワーク（π_new）で、バッファに入っている **同じ行動** の log_prob を再計算
        dist = self.actor.squashed_dist(mb_obs)
        new_log_probs = self._squashed_log_prob(dist, mb_actions_sel)
        if not torch.isfinite(new_log_probs).all():
          continue

        # 方策比 r = π_new(a|s) / π_old(a|s)  （log 空間では exp(new - old)）
        ratio = torch.exp(new_log_probs - mb_old_log_probs)

        # PPO-Clip の核心:
        #   L = -min( r * A,  clip(r, 1-ε, 1+ε) * A )
        # A>0（良い行動）: r を大きくしすぎない（1+ε で頭打ち）
        # A<0（悪い行動）: r を小さくしすぎない（1-ε で床）
        surr1 = ratio * mb_adv
        surr2 = (
          torch.clamp(
            ratio,
            1.0 - float(ppo_cfg.clip_eps),
            1.0 + float(ppo_cfg.clip_eps),
          )
          * mb_adv
        )
        policy_loss = -torch.min(surr1, surr2).mean()

        # Critic: V(s) が GAE の return に近づくよう MSE（方策とは別の頭）
        new_values = self.critic(mb_obs)
        value_loss = nn.functional.mse_loss(new_values, mb_returns)

        # Entropy ボーナス: 探索を残す（係数 ENTROPY_COEF で減算＝最大化）
        loc, std = self.actor(mb_obs)
        entropy = self.actor.gaussian_entropy(loc, std)

        loss = (
          policy_loss
          + float(ppo_cfg.value_coef) * value_loss
          - float(ppo_cfg.entropy_coef) * entropy
        )
        if not torch.isfinite(loss):
          continue

        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(
          list(self.actor.parameters()) + list(self.critic.parameters()),
          float(ppo_cfg.max_grad_norm),
        )
        if not all(
          torch.isfinite(p.grad).all()
          for p in list(self.actor.parameters()) + list(self.critic.parameters())
          if p.grad is not None
        ):
          self.optimizer.zero_grad()
          continue
        self.optimizer.step()

        # 監視用（wandb）: 方策がどれだけ変わったかの近似 KL、clip が効いた割合
        with torch.no_grad():
          approx_kl = (mb_old_log_probs - new_log_probs).mean().item()
          clip_fraction = (
            (torch.abs(ratio - 1.0) > float(ppo_cfg.clip_eps)).float().mean().item()
          )

        total_policy_loss += policy_loss.item()
        total_value_loss += value_loss.item()
        total_entropy += entropy.item()
        total_approx_kl += approx_kl
        total_clip_fraction += clip_fraction
        epoch_kl += approx_kl
        n_mb += 1
        epoch_mb += 1

      # 方策が大きく変わりすぎた epoch 以降は打ち切り（過学習・崩壊の抑制）
      if (
        float(ppo_cfg.target_kl) > 0.0
        and epoch_mb > 0
        and (epoch_kl / epoch_mb) > float(ppo_cfg.target_kl)
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
    ctx: ExperimentContext,
    path: str | Path,
    *,
    lr: float | None = None,
    load_optimizer: bool = True,
    map_location: str | torch.device = "cpu",
  ) -> AgentPPO:
    """保存済みチェックポイントからエージェントを復元する。"""
    import rl.checkpoint as checkpoint

    payload = checkpoint.load_checkpoint(path, map_location=map_location)
    fmt = payload.get("format", "")
    if fmt and fmt not in checkpoint.COMPATIBLE_CHECKPOINT_FORMATS:
      raise ValueError(
        f"checkpoint format {fmt!r} not in {checkpoint.COMPATIBLE_CHECKPOINT_FORMATS!r}"
      )
    sim_cfg = ctx.cfg.sim
    expected_obs_dim = int(sim_cfg.obs_dim)
    expected_action_dim = int(sim_cfg.action_dim)
    expected_hidden_sizes = tuple(int(x) for x in sim_cfg.policy_hidden_sizes)

    obs_dim = int(payload["obs_dim"])
    action_dim = int(payload["action_dim"])
    if obs_dim != expected_obs_dim:
      raise ValueError(
        f"checkpoint obs_dim={obs_dim} does not match cfg.sim.obs_dim={expected_obs_dim}"
      )
    if action_dim != expected_action_dim:
      raise ValueError(
        f"checkpoint action_dim={action_dim} does not match cfg.sim.action_dim={expected_action_dim}"
      )
    raw_hidden = payload.get("policy_hidden_sizes")
    if raw_hidden is not None:
      hidden_sizes = tuple(int(x) for x in raw_hidden)
    else:
      hidden_sizes = expected_hidden_sizes
    if hidden_sizes != expected_hidden_sizes:
      raise ValueError(
        f"checkpoint policy_hidden_sizes={hidden_sizes} "
        f"does not match cfg.sim.policy_hidden_sizes={expected_hidden_sizes}"
      )
    agent = cls(ctx)
    agent.actor.load_state_dict(payload["actor"])
    agent.critic.load_state_dict(payload["critic"])
    if lr is not None:
      agent.set_learning_rate(lr)
    elif load_optimizer and "optimizer" in payload:
      agent.optimizer.load_state_dict(payload["optimizer"])
    return agent


