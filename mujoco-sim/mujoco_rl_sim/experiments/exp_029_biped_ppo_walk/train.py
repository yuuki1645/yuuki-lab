"""exp_029 学習エントリ（交互片脚歩行・拡大 MLP・スタンドアロン ``contract`` 同梱）。

本ファイルは薄いラッパー。学習ループ本体は ``contract.session.run_ppo_train`` にあり、
実験固有の差し替え点（環境・エージェント・W&B）だけを ``PpoTrainBindings`` で渡す。

実行::

  python train.py
  python train.py --resume path/to/latest.pt
  python train.py --set forward_reward_scale=55 --set reward_enable_walk_shaping=true
"""

from __future__ import annotations

from _paths import install

install()

from pathlib import Path
from typing import Any

import config
import json
import os

from contract import TELEMETRY_CONTRACT, PpoTrainBindings, run_ppo_train
from eval.post_train import run_post_train_eval
from lib.config_overrides import apply_cli_set_overrides, apply_dispatch_env_overrides
from lib.run_config_snapshot import (
  build_effective_config_snapshot,
  write_config_effective_json,
)
from lib.training_seed import apply_training_seed, resolve_training_seed
from package_meta import EXP_NAME
import rl.checkpoint as checkpoint
import rl.wandb_logging as wandb_logging
from rl.agent import AgentPPO
from rl.run_config import TrainRunConfig, parse_train_args
import sim.warmup as warmup
from sim.env import EnvBipedPPO


def _dispatch_overrides_for_logging() -> dict[str, Any]:
  """W&B 用: 環境変数 DISPATCH_CONFIG_OVERRIDES_JSON の内容（未適用の生 dict）。"""
  raw = os.environ.get("DISPATCH_CONFIG_OVERRIDES_JSON", "").strip()
  if not raw:
    return {}
  payload = json.loads(raw)
  return payload if isinstance(payload, dict) else {}


def _load_resume_state(resume_path: Path) -> dict[str, Any]:
  return checkpoint.load_checkpoint(resume_path, map_location="cpu")


def _create_agent(run: TrainRunConfig) -> tuple[AgentPPO, dict[str, Any] | None]:
  if run.resume_path is None:
    agent = AgentPPO(obs_dim=config.OBS_DIM)
    if run.lr is not None:
      agent.set_learning_rate(run.lr)
    return agent, None

  payload = _load_resume_state(run.resume_path)
  agent = AgentPPO.from_checkpoint(
    run.resume_path,
    lr=run.lr,
    load_optimizer=run.load_optimizer,
  )
  return agent, payload


def _wandb_init(
  run: TrainRunConfig,
  payload: dict[str, Any] | None,
  *,
  applied_config_overrides: dict[str, Any],
  training_dr_effective: bool,
) -> None:
  extra_config: dict[str, Any] | None = None
  extra_tags: tuple[str, ...] | None = None
  run_name = run.wandb_run_name

  if payload is not None:
    base_update = int(payload.get("update", 0))
    base_env_steps = int(payload.get("total_env_steps", 0))
    base_episodes = int(payload.get("episodes_finished", 0))
    extra_config = {
      "resume_checkpoint": str(run.resume_path),
      "resume_base_update": base_update,
      "resume_base_env_steps": base_env_steps,
      "resume_base_episodes_finished": base_episodes,
      "num_updates_this_run": run.num_updates,
      "end_update_target": base_update + run.num_updates,
      "telemetry_schema": TELEMETRY_CONTRACT.schema_id,
      "contract_package": "contract",
    }
    if run.lr is not None:
      extra_config["lr"] = run.lr
      extra_config["lr_overridden"] = True
    else:
      extra_config["lr_overridden"] = False
    extra_tags = ("finetune", "resume", "contract")
    if run_name is None:
      lr_tag = f"lr{run.lr:g}" if run.lr is not None else "lr_ckpt"
      run_name = f"resume_u{base_update:06d}_{lr_tag}"
  else:
    extra_config = {
      "telemetry_schema": TELEMETRY_CONTRACT.schema_id,
      "contract_package": "contract",
    }
    extra_tags = ("contract",)

  training_seed = resolve_training_seed(cli_seed=run.training_seed)
  if training_seed is not None:
    extra_config = dict(extra_config)
    extra_config["training_seed"] = training_seed
  extra_config = dict(extra_config or {})
  extra_config["training_dr"] = bool(training_dr_effective)

  if applied_config_overrides:
    extra_config = dict(extra_config)
    extra_config["config_overrides"] = applied_config_overrides
    if run.config_set_args:
      extra_config["cli_config_set_args"] = list(run.config_set_args)
    dispatch_raw = _dispatch_overrides_for_logging()
    if dispatch_raw:
      extra_config["dispatch_config_overrides_env"] = dispatch_raw

  wandb_logging.init(
    extra_config=extra_config,
    extra_tags=extra_tags,
    run_name=run_name,
    enabled=run.wandb,
  )


def _apply_run_config_overrides(run: TrainRunConfig) -> dict[str, Any]:
  """dispatch 環境変数 → CLI --set の順で config を上書き（後勝ち）。"""
  applied: dict[str, Any] = {}
  applied.update(apply_dispatch_env_overrides())
  applied.update(apply_cli_set_overrides(run.config_set_args))
  return applied


def _make_on_checkpoint_run_dir(
  run: TrainRunConfig,
  *,
  applied_config_overrides: dict[str, Any],
):
  """``config_effective.json`` を run ディレクトリへ書き出すコールバックを返す。"""

  def _on_checkpoint_run_dir(
    run_dir: Path,
    resume_payload: dict[str, Any] | None,
    agent: AgentPPO,
  ) -> None:
    snapshot = build_effective_config_snapshot(
      run,
      agent,
      applied_config_overrides=applied_config_overrides,
      resume_payload=resume_payload,
      exp_name=EXP_NAME,
      telemetry_schema=TELEMETRY_CONTRACT.schema_id,
    )
    out_path = write_config_effective_json(run_dir, snapshot)
    print(f"[config] saved effective config -> {out_path}")

  return _on_checkpoint_run_dir


def main() -> None:
  run = parse_train_args()
  applied_overrides = _apply_run_config_overrides(run)
  training_dr_effective = bool(config.TRAINING_DR_ENABLED) and bool(run.training_dr)

  training_seed = resolve_training_seed(cli_seed=run.training_seed)
  if training_seed is not None:
    apply_training_seed(training_seed)
    print(f"[seed] training seed={training_seed}")
  else:
    print("[seed] training seed not set (non-deterministic run)")

  eval_report: dict[str, Any] | None = None
  try:
    eval_report = _run_training(
      run,
      applied_overrides,
      training_dr_effective=training_dr_effective,
    )
  finally:
    if eval_report is not None:
      wandb_logging.log_eval_report(eval_report)
    wandb_logging.finish()


def _run_training(
  run: TrainRunConfig,
  applied_overrides: dict[str, Any],
  *,
  training_dr_effective: bool,
) -> dict[str, Any] | None:
  def init_wandb(run_cfg: TrainRunConfig, payload: dict[str, Any] | None) -> None:
    _wandb_init(
      run_cfg,
      payload,
      applied_config_overrides=applied_overrides,
      training_dr_effective=training_dr_effective,
    )

  resolved_seed = resolve_training_seed(cli_seed=run.training_seed)

  def _env_factory(viewer: bool) -> EnvBipedPPO:
    return EnvBipedPPO(
      enable_viewer=viewer,
      training_dr_enabled=training_dr_effective,
      training_seed=resolved_seed,
    )

  bindings = PpoTrainBindings(
    config=config,
    checkpoint=checkpoint,
    wandb_logging=wandb_logging,
    warmup=warmup,
    exp_name=EXP_NAME,
    telemetry=TELEMETRY_CONTRACT,
    env_factory=_env_factory,
    create_agent=_create_agent,
    init_wandb=init_wandb,
    on_checkpoint_run_dir=_make_on_checkpoint_run_dir(
      run,
      applied_config_overrides=applied_overrides,
    ),
    train_run_config=run,
    training_dr_enabled=training_dr_effective,
    training_seed_resolved=resolved_seed,
  )
  train_result = run_ppo_train(bindings)
  return _maybe_run_post_train_eval(run, train_result)


def _maybe_run_post_train_eval(run: TrainRunConfig, train_result) -> dict[str, Any] | None:
  """学習完了後に ``final.pt`` で eval v0 を実行する（``--no-eval`` でスキップ）。"""
  if not run.post_train_eval:
    print("[eval] post-train eval skipped (--no-eval)")
    return None

  final_ckpt = train_result.final_checkpoint_path
  if final_ckpt is None:
    print("[eval] post-train eval skipped (no final checkpoint saved)")
    return None

  _out_path, report = run_post_train_eval(final_ckpt)
  return report


if __name__ == "__main__":
  main()
