"""実験 train.py のサブプロセス実行。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mujoco_rl_sim.dispatch.common.primary_metric import metric_from_summary_file
from mujoco_rl_sim.dispatch.paths import experiment_dir


def _git_commit(cwd: Path) -> str | None:
  try:
    out = subprocess.run(
      ["git", "rev-parse", "HEAD"],
      cwd=cwd,
      capture_output=True,
      text=True,
      check=True,
      timeout=10,
    )
    return out.stdout.strip() or None
  except (OSError, subprocess.CalledProcessError):
    return None


def build_train_command(job: dict[str, Any], *, exp_path: Path) -> list[str]:
  overrides: dict[str, Any] = job.get("overrides") or {}
  cmd = [sys.executable, "train.py", "--no-viewer", "--no-telemetry"]
  run_name = job["run_id"]
  cmd.extend(["--wandb-run-name", run_name])

  if "lr" in overrides:
    cmd.extend(["--lr", str(overrides["lr"])])
  if "num_updates" in overrides:
    cmd.extend(["--num-updates", str(int(overrides["num_updates"]))])
  if overrides.get("wandb") is False:
    cmd.append("--no-wandb")
  elif overrides.get("wandb") is True:
    cmd.append("--wandb")

  return cmd


def build_job_env(job: dict[str, Any]) -> dict[str, str]:
  env = os.environ.copy()
  env["DISPATCH_RUN_ID"] = job["run_id"]
  env["DISPATCH_SWEEP_ID"] = job["sweep_id"]
  env["DISPATCH_CONFIG_HASH"] = job["config_hash"]
  env["DISPATCH_WANDB_GROUP"] = job["config_hash"]
  tags = f"sweep:{job['sweep_id']},worker:dispatch"
  env["DISPATCH_WANDB_EXTRA_TAGS"] = tags
  seed = job.get("overrides", {}).get("seed")
  if seed is not None:
    env["DISPATCH_SEED"] = str(seed)
  return env


def run_train_job(
  job: dict[str, Any],
  *,
  mujoco_rl_sim_root: Path,
) -> tuple[int, str, float | None, str | None]:
  """終了コード, ログ要約, primary_metric, artifact_path を返す。"""
  exp_id = job["exp_id"]
  exp_path = experiment_dir(exp_id)
  cmd = build_train_command(job, exp_path=exp_path)
  env = build_job_env(job)
  repo_root = mujoco_rl_sim_root.parent

  proc = subprocess.run(
    cmd,
    cwd=exp_path,
    env=env,
    capture_output=True,
    text=True,
    timeout=None,
  )
  log_tail = (proc.stderr or proc.stdout or "")[-2000:]
  primary: float | None = None
  artifact_path: str | None = None

  summary_path = exp_path / "dispatch_summary.json"
  if summary_path.is_file():
    try:
      data = json.loads(summary_path.read_text(encoding="utf-8"))
      primary = metric_from_summary_file(data)
      artifact_path = data.get("artifact_path")
    except (json.JSONDecodeError, OSError):
      pass

  if primary is None:
    runs_dir = mujoco_rl_sim_root / "runs" / exp_id
    candidate = runs_dir / job["run_id"] / "dispatch_summary.json"
    if candidate.is_file():
      try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
        primary = metric_from_summary_file(data)
        artifact_path = data.get("artifact_path") or str(candidate.parent)
      except (json.JSONDecodeError, OSError):
        pass

  git_commit = _git_commit(repo_root)
  if proc.returncode != 0:
    return proc.returncode, log_tail, None, artifact_path

  return proc.returncode, log_tail, primary, artifact_path or str(exp_path)
