"""run 開始時の effective config を ``config_effective.json`` として checkpoint run dir に保存する。"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import config
from lib.config_overrides import OVERRIDABLE_CONFIG_KEYS
from lib.training_seed import resolve_training_seed
from package_meta import MUJOCO_RL_SIM_ROOT
from sim.domain_randomization import training_dr_spec_dict

CONFIG_EFFECTIVE_FILENAME = "config_effective.json"
_SCHEMA_VERSION = 1


def _json_value(value: Any) -> Any:
  """JSON 化可能な形に正規化する（tuple → list など）。"""
  if isinstance(value, tuple):
    return [_json_value(v) for v in value]
  if isinstance(value, Path):
    return str(value)
  if isinstance(value, dict):
    return {str(k): _json_value(v) for k, v in value.items()}
  if isinstance(value, list):
    return [_json_value(v) for v in value]
  return value


def _effective_step_wall_sleep_sec(run: Any) -> float:
  """``TrainRunConfig`` と config 既定から、この run の壁時計 sleep [s] を求める。"""
  if run.step_wall_sleep_sec is not None:
    return float(run.step_wall_sleep_sec)
  if run.viewer:
    return float(config.STEP_WALL_SLEEP_SEC)
  return 0.0


def _agent_learning_rate(agent: Any) -> float:
  """optimizer に設定済みの学習率（--lr / checkpoint 反映後）。"""
  return float(agent.optimizer.param_groups[0]["lr"])


def _git_commit() -> str | None:
  """再現性のため git HEAD（取得失敗時は None）。"""
  try:
    out = subprocess.run(
      ["git", "rev-parse", "HEAD"],
      cwd=MUJOCO_RL_SIM_ROOT.parent,
      capture_output=True,
      text=True,
      check=True,
      timeout=10,
    )
    return out.stdout.strip() or None
  except (OSError, subprocess.CalledProcessError):
    return None


def _dispatch_env_metadata() -> dict[str, Any]:
  """dispatch Worker が渡す環境変数（該当時のみ）。"""
  fields = (
    "DISPATCH_RUN_ID",
    "DISPATCH_SWEEP_ID",
    "DISPATCH_CONFIG_HASH",
    "DISPATCH_SEED",
  )
  meta: dict[str, Any] = {}
  for name in fields:
    value = os.environ.get(name, "").strip()
    if value:
      meta[name.removeprefix("DISPATCH_").lower()] = value
  raw = os.environ.get("DISPATCH_CONFIG_OVERRIDES_JSON", "").strip()
  if raw:
    try:
      payload = json.loads(raw)
      if isinstance(payload, dict):
        meta["config_overrides_env"] = payload
    except json.JSONDecodeError:
      meta["config_overrides_env_raw"] = raw
  return meta


def build_effective_config_snapshot(
  run: Any,
  agent: Any,
  *,
  applied_config_overrides: dict[str, Any],
  resume_payload: dict[str, Any] | None,
  exp_name: str,
  telemetry_schema: str,
) -> dict[str, Any]:
  """この run が実際に使う設定のスナップショット dict を組み立てる。"""
  training = _json_value(config.training_config_dict())

  # training_config_dict は config モジュール参照のため、run CLI / agent の実効値で上書き
  training["lr"] = _agent_learning_rate(agent)
  training["num_updates"] = int(run.num_updates)
  training["enable_viewer"] = bool(run.viewer)
  training["telemetry_enabled"] = bool(run.telemetry)
  training["telemetry_host"] = str(run.telemetry_host)
  training["telemetry_port"] = int(run.telemetry_port)
  training["step_wall_sleep_sec"] = _effective_step_wall_sleep_sec(run)
  training["use_wandb"] = bool(run.wandb)

  # training_config_dict に無い overridable キーも含める
  for snake_key, attr in OVERRIDABLE_CONFIG_KEYS.items():
    if snake_key not in training:
      training[snake_key] = _json_value(getattr(config, attr))

  snapshot: dict[str, Any] = {
    "schema_version": _SCHEMA_VERSION,
    "exp_name": exp_name,
    "telemetry_schema": telemetry_schema,
    "git_commit": _git_commit(),
    "training_config": training,
    "run_cli": _json_value(
      {
        "resume_path": str(run.resume_path) if run.resume_path is not None else None,
        "lr_cli": run.lr,
        "num_updates": run.num_updates,
        "load_optimizer": run.load_optimizer,
        "wandb_run_name": run.wandb_run_name,
        "viewer": run.viewer,
        "telemetry": run.telemetry,
        "wandb": run.wandb,
        "telemetry_host": run.telemetry_host,
        "telemetry_port": run.telemetry_port,
        "step_wall_sleep_sec": run.step_wall_sleep_sec,
        "config_set_args": list(run.config_set_args),
        "training_seed": run.training_seed,
        "training_dr_cli": bool(getattr(run, "training_dr", True)),
      }
    ),
    "training_dr_spec": _training_dr_spec_for_run(run),
  }

  if applied_config_overrides:
    snapshot["config_overrides_applied"] = _json_value(applied_config_overrides)

  dispatch_meta = _dispatch_env_metadata()
  if dispatch_meta:
    snapshot["dispatch"] = dispatch_meta

  effective_training_seed = resolve_training_seed(cli_seed=run.training_seed)
  if effective_training_seed is not None:
    snapshot["training_seed"] = int(effective_training_seed)

  if resume_payload is not None:
    snapshot["resume"] = _json_value(
      {
        "checkpoint": str(run.resume_path) if run.resume_path is not None else None,
        "base_update": int(resume_payload.get("update", 0)),
        "base_total_env_steps": int(resume_payload.get("total_env_steps", 0)),
        "base_episodes_finished": int(resume_payload.get("episodes_finished", 0)),
        "end_update_target": int(resume_payload.get("update", 0)) + int(run.num_updates),
      }
    )

  return snapshot


def _training_dr_spec_for_run(run: Any) -> dict[str, Any]:
  """実効 DR 設定（config 上書き後の TRAINING_DR_ENABLED を反映）。"""
  spec = training_dr_spec_dict()
  spec["enabled"] = bool(config.TRAINING_DR_ENABLED) and bool(
    getattr(run, "training_dr", True)
  )
  return spec


def write_config_effective_json(
  run_dir: Path,
  snapshot: dict[str, Any],
) -> Path:
  """``run_dir/config_effective.json`` を書き出す。"""
  run_dir.mkdir(parents=True, exist_ok=True)
  out_path = run_dir / CONFIG_EFFECTIVE_FILENAME
  out_path.write_text(
    json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
  )
  return out_path
