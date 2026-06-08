"""exp_030 学習エントリ（Hydra 設定・交互片脚歩行 PPO）。

実行例（本フォルダで）::

  python train.py
  python train.py training=smoke runtime=fast reward=forward55
  python train.py wandb=disabled training.num_updates=1
  python train.py resume.checkpoint=../../runs/exp_030_biped_ppo_walk/<run>/latest.pt
"""

from __future__ import annotations

from _paths import install

install()

from lib.dispatch_argv_bridge import bridge_legacy_argv_for_hydra

bridge_legacy_argv_for_hydra()

import json
import os
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from conf.schema import build_app_config
from conf.schema.register import register_config_store
from contract import PpoTrainBindings, run_ppo_train
from eval.post_train import run_post_train_eval
from lib.dispatch_cfg_merge import merge_dispatch_overrides
from lib.experiment_context import ExperimentContext, build_experiment_context
from lib.hydra_checkpoint import save_hydra_config
from lib.hydra_compose import cfg_to_dict
from lib.training_seed import apply_training_seed, resolve_training_seed
import rl.checkpoint as checkpoint
import rl.wandb_logging as wandb_logging
from rl.agent import AgentPPO
import sim.warmup as warmup
from sim.env import EnvBipedPPO

register_config_store()


def _apply_dispatch_seed(cfg: DictConfig) -> None:
  """dispatch が渡す ``DISPATCH_SEED`` を training.seed へ反映する。"""
  if cfg.training.seed is not None:
    return
  raw = os.environ.get("DISPATCH_SEED", "").strip()
  if raw:
    OmegaConf.update(cfg, "training.seed", int(raw), merge=False)


def _resolve_resume_path(ctx: ExperimentContext) -> Path | None:
  raw = ctx.cfg.resume.checkpoint
  if raw is None or not str(raw).strip():
    return None
  return checkpoint.resolve_checkpoint_path(str(raw))


def _create_agent(ctx: ExperimentContext) -> tuple[AgentPPO, dict[str, Any] | None]:
  resume_path = _resolve_resume_path(ctx)
  if resume_path is None:
    agent = AgentPPO(ctx)
    resume_lr = ctx.cfg.resume.lr
    if resume_lr is not None:
      agent.set_learning_rate(float(resume_lr))
    return agent, None

  payload = checkpoint.load_checkpoint(resume_path, map_location="cpu")
  agent = AgentPPO.from_checkpoint(
    ctx,
    resume_path,
    lr=ctx.cfg.resume.lr,
    load_optimizer=ctx.cfg.resume.load_optimizer,
  )
  return agent, payload


def _wandb_init(
  ctx: ExperimentContext,
  payload: dict[str, Any] | None,
  *,
  training_dr_effective: bool,
  dispatch_raw: dict[str, Any],
) -> None:
  extra_config: dict[str, Any] = {
    "telemetry_schema": ctx.telemetry_schema,
    "contract_package": "contract",
    "hydra_config": cfg_to_dict(ctx.cfg),
    "training_dr": bool(training_dr_effective),
  }
  extra_tags: tuple[str, ...] = ("contract",)
  run_name = ctx.cfg.wandb.run_name.strip() or None

  if payload is not None:
    base_update = int(payload.get("update", 0))
    extra_config.update(
      {
        "resume_checkpoint": str(_resolve_resume_path(ctx)),
        "resume_base_update": base_update,
        "resume_base_env_steps": int(payload.get("total_env_steps", 0)),
        "resume_base_episodes_finished": int(payload.get("episodes_finished", 0)),
        "num_updates_this_run": int(ctx.cfg.training.num_updates),
        "end_update_target": base_update + int(ctx.cfg.training.num_updates),
      }
    )
    resume_lr = ctx.cfg.resume.lr
    if resume_lr is not None:
      extra_config["lr"] = float(resume_lr)
      extra_config["lr_overridden"] = True
    else:
      extra_config["lr_overridden"] = False
    extra_tags = ("finetune", "resume", "contract")
    if run_name is None:
      lr_tag = f"lr{resume_lr:g}" if resume_lr is not None else "lr_ckpt"
      run_name = f"resume_u{base_update:06d}_{lr_tag}"

  training_seed = resolve_training_seed(cli_seed=ctx.cfg.training.seed)
  if training_seed is not None:
    extra_config["training_seed"] = training_seed
  if dispatch_raw:
    extra_config["dispatch_config_overrides_env"] = dispatch_raw

  wandb_logging.init(
    ctx,
    extra_config=extra_config,
    extra_tags=extra_tags,
    run_name=run_name,
  )

def _dispatch_overrides_for_logging() -> dict[str, Any]:
  raw = os.environ.get("DISPATCH_CONFIG_OVERRIDES_JSON", "").strip()
  if not raw:
    return {}
  payload = json.loads(raw)
  return payload if isinstance(payload, dict) else {}


@hydra.main(version_base=None, config_path="conf", config_name="config")
def main(cfg: DictConfig) -> None:
  cfg = merge_dispatch_overrides(cfg)
  _apply_dispatch_seed(cfg)
  app_cfg = build_app_config(cfg)
  ctx = build_experiment_context(app_cfg)

  if ctx.cfg.runtime.num_envs < 1:
    raise SystemExit("runtime.num_envs は 1 以上にしてください")

  runtime = ctx.cfg.runtime
  if runtime.num_envs > 1 and (runtime.viewer or runtime.telemetry):
    print(
      "[subproc-vec] num_envs>1: viewer/telemetry を無効化します "
      "(runtime=fast 推奨)"
    )
    runtime.viewer = False
    runtime.telemetry = False

  training_dr_effective = bool(ctx.cfg.training.training_dr)
  training_seed = resolve_training_seed(cli_seed=ctx.cfg.training.seed)
  if training_seed is not None:
    apply_training_seed(training_seed)
    print(f"[seed] training seed={training_seed}")
  else:
    print("[seed] training seed not set (non-deterministic run)")

  dispatch_raw = _dispatch_overrides_for_logging()
  eval_report: dict[str, Any] | None = None

  try:
    eval_report = _run_training(
      ctx,
      resolved_cfg=cfg,
      training_dr_effective=training_dr_effective,
      training_seed=training_seed,
      dispatch_raw=dispatch_raw,
    )
  finally:
    if eval_report is not None:
      wandb_logging.log_eval_report(eval_report)
    wandb_logging.finish()


def _run_training(
  ctx: ExperimentContext,
  *,
  resolved_cfg: DictConfig,
  training_dr_effective: bool,
  training_seed: int | None,
  dispatch_raw: dict[str, Any],
) -> dict[str, Any] | None:
  """学習本体。"""

  def init_wandb(_ctx: ExperimentContext, payload: dict[str, Any] | None) -> None:
    _wandb_init(
      _ctx,
      payload,
      training_dr_effective=training_dr_effective,
      dispatch_raw=dispatch_raw,
    )

  def env_factory(viewer: bool) -> EnvBipedPPO:
    return EnvBipedPPO(
      ctx,
      enable_viewer=viewer,
      training_dr_enabled=training_dr_effective,
      training_seed=training_seed,
    )

  bindings: PpoTrainBindings

  def on_checkpoint_run_dir(run_dir: Path) -> None:
    if bindings.resolved_cfg is None:
      return
    # session 側で run_dir 作成直後に 1 回だけ呼ぶ。
    out = save_hydra_config(run_dir, bindings.resolved_cfg)
    print(f"[hydra] saved effective config -> {out}")

  bindings = PpoTrainBindings(
    ctx=ctx,
    resolved_cfg=resolved_cfg,
    checkpoint=checkpoint,
    wandb_logging=wandb_logging,
    warmup=warmup,
    env_factory=env_factory,
    create_agent=_create_agent,
    init_wandb=init_wandb,
    on_checkpoint_run_dir=on_checkpoint_run_dir,
    training_dr_enabled=training_dr_effective,
    training_seed_resolved=training_seed,
  )
  train_result = run_ppo_train(bindings)
  return _maybe_run_post_train_eval(ctx, train_result)


def _maybe_run_post_train_eval(
  ctx: ExperimentContext,
  train_result,
) -> dict[str, Any] | None:
  if not ctx.cfg.training.post_train_eval:
    print("[eval] post-train eval skipped (training.post_train_eval=false)")
    return None
  final_ckpt = train_result.final_checkpoint_path
  if final_ckpt is None:
    print("[eval] post-train eval skipped (no final checkpoint saved)")
    return None
  _out_path, report = run_post_train_eval(final_ckpt)
  return report


if __name__ == "__main__":
  main()
