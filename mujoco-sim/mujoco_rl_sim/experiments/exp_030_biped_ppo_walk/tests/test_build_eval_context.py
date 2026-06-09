"""``build_eval_context`` の単体テスト（Hydra 再初期化なし）。"""

from __future__ import annotations

from lib.hydra_compose import compose_app_config
from lib.load_run_context import build_eval_app_config, build_eval_context


def test_build_eval_app_config_disables_wandb_and_training_dr() -> None:
  base = compose_app_config(["wandb=enabled", "training.training_dr=true"])
  eval_cfg = build_eval_app_config(base)

  assert eval_cfg.wandb.enabled is False
  assert eval_cfg.training.training_dr is False
  # 学習時の報酬設定などは引き継ぐ
  assert eval_cfg.reward == base.reward


def test_build_eval_context_preserves_reward_override() -> None:
  base = compose_app_config(["reward.forward_reward_scale=99.0"])
  ctx = build_eval_context(base)

  assert ctx.cfg.wandb.enabled is False
  assert ctx.cfg.training.training_dr is False
  assert ctx.cfg.reward.forward_reward_scale == 99.0


def test_build_eval_app_config_syncs_ppo_sim_reference() -> None:
  base = compose_app_config()
  eval_cfg = build_eval_app_config(base)

  assert eval_cfg.ppo._sim is eval_cfg.sim
