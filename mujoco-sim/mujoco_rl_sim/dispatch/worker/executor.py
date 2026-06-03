"""実験 train.py のサブプロセス実行。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mujoco_rl_sim.dispatch.common.primary_metric import metric_from_summary_file
from mujoco_rl_sim.dispatch.common.progress import (
  dispatch_progress_path_for_job,
  read_dispatch_progress,
)
from mujoco_rl_sim.dispatch.paths import experiment_dir

_PROGRESS_POLL_SEC = 2.0


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


_TRAIN_CLI_OVERRIDE_KEYS = frozenset({"seed", "lr", "num_updates", "wandb"})


def _config_overrides_for_env(overrides: dict[str, Any]) -> dict[str, Any]:
  return {k: v for k, v in overrides.items() if k not in _TRAIN_CLI_OVERRIDE_KEYS}


def build_train_command(job: dict[str, Any], *, exp_path: Path) -> list[str]:
  overrides: dict[str, Any] = job.get("overrides") or {}
  cmd = [sys.executable, "train.py", "--no-viewer", "--no-telemetry", "--step-wall-sleep", "0"]
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


def build_job_env(job: dict[str, Any], *, progress_path: Path) -> dict[str, str]:
  env = os.environ.copy()
  env["DISPATCH_RUN_ID"] = job["run_id"]
  env["DISPATCH_SWEEP_ID"] = job["sweep_id"]
  env["DISPATCH_CONFIG_HASH"] = job["config_hash"]
  env["DISPATCH_WANDB_GROUP"] = job["config_hash"]
  env["DISPATCH_PROGRESS_FILE"] = str(progress_path)
  tags = f"sweep:{job['sweep_id']},worker:dispatch"
  env["DISPATCH_WANDB_EXTRA_TAGS"] = tags
  seed = job.get("overrides", {}).get("seed")
  if seed is not None:
    env["DISPATCH_SEED"] = str(seed)
  cfg_overrides = _config_overrides_for_env(job.get("overrides") or {})
  if cfg_overrides:
    env["DISPATCH_CONFIG_OVERRIDES_JSON"] = json.dumps(
      cfg_overrides, ensure_ascii=False, sort_keys=True
    )
  return env


def _read_log_tail(path: Path, *, max_chars: int = 2000) -> str:
  try:
    text = path.read_text(encoding="utf-8", errors="replace")
  except OSError:
    return ""
  return text[-max_chars:]


def run_train_job(
  job: dict[str, Any],
  *,
  mujoco_rl_sim_root: Path,
  on_progress: Callable[[dict[str, int]], None] | None = None,
) -> tuple[int, str, float | None, str | None]:
  """終了コード, ログ要約, primary_metric, artifact_path を返す。"""
  exp_id = job["exp_id"]
  exp_path = experiment_dir(exp_id)
  cmd = build_train_command(job, exp_path=exp_path)
  progress_path = dispatch_progress_path_for_job(job, mujoco_rl_sim_root=mujoco_rl_sim_root)
  progress_path.parent.mkdir(parents=True, exist_ok=True)
  env = build_job_env(job, progress_path=progress_path)
  repo_root = mujoco_rl_sim_root.parent
  run_id = str(job["run_id"])

  with tempfile.TemporaryDirectory(prefix="dispatch-train-") as tmpdir:
    log_path = Path(tmpdir) / "train.log"
    with log_path.open("w", encoding="utf-8") as log_file:
      proc = subprocess.Popen(
        cmd,
        cwd=exp_path,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
      )
      last_progress: dict[str, int] | None = None
      while proc.poll() is None:
        prog = read_dispatch_progress(progress_path, run_id=run_id)
        if prog is None:
          fallback = exp_path / "dispatch_progress.json"
          prog = read_dispatch_progress(fallback, run_id=run_id)
        if prog is not None and prog != last_progress:
          last_progress = prog
          if on_progress is not None:
            on_progress(prog)
        time.sleep(_PROGRESS_POLL_SEC)

      code = int(proc.wait())

    log_tail = _read_log_tail(log_path)

  primary: float | None = None
  artifact_path: str | None = None

  summary_path = exp_path / "dispatch_summary.json"
  if summary_path.is_file():
    try:
      data = json.loads(summary_path.read_text(encoding="utf-8"))
      if str(data.get("dispatch_run_id", "")).strip() in ("", run_id):
        primary = metric_from_summary_file(data)
        artifact_path = data.get("artifact_path")
    except (json.JSONDecodeError, OSError):
      pass

  if primary is None:
    runs_dir = mujoco_rl_sim_root / "runs" / exp_id
    candidate = runs_dir / run_id / "dispatch_summary.json"
    if candidate.is_file():
      try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
        primary = metric_from_summary_file(data)
        artifact_path = data.get("artifact_path") or str(candidate.parent)
      except (json.JSONDecodeError, OSError):
        pass

  _git_commit(repo_root)
  if code != 0:
    return code, log_tail, None, artifact_path

  return code, log_tail, primary, artifact_path or str(exp_path)
