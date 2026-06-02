"""dispatch ジョブ進捗（update 数）のファイル I/O。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mujoco_rl_sim.dispatch.paths import MUJOCO_RL_SIM_ROOT


def _utc_iso() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dispatch_progress_path_for_job(job: dict[str, Any], *, mujoco_rl_sim_root: Path | None = None) -> Path:
  """Worker が監視する進捗ファイルパス（run ごとに一意）。"""
  root = mujoco_rl_sim_root or MUJOCO_RL_SIM_ROOT
  exp_id = str(job["exp_id"])
  run_id = str(job["run_id"])
  return root / "runs" / exp_id / run_id / "dispatch_progress.json"


def _progress_path_for_write() -> Path | None:
  raw = os.environ.get("DISPATCH_PROGRESS_FILE", "").strip()
  if raw:
    return Path(raw)
  run_id = os.environ.get("DISPATCH_RUN_ID", "").strip()
  if not run_id:
    return None
  return Path.cwd() / "dispatch_progress.json"


def write_dispatch_progress(*, current_update: int, total_updates: int) -> None:
  """train ループから進捗 JSON を書き出す（DISPATCH_RUN_ID 未設定時は no-op）。"""
  run_id = os.environ.get("DISPATCH_RUN_ID", "").strip()
  if not run_id:
    return
  path = _progress_path_for_write()
  if path is None:
    return
  payload = {
    "dispatch_run_id": run_id,
    "current_update": int(current_update),
    "total_updates": int(total_updates),
    "updated_at": _utc_iso(),
  }
  path.parent.mkdir(parents=True, exist_ok=True)
  tmp = path.with_suffix(".json.tmp")
  tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
  tmp.replace(path)


def read_dispatch_progress(
  path: Path,
  *,
  run_id: str | None = None,
) -> dict[str, int] | None:
  """進捗ファイルを読む。run_id が一致しない場合は None。"""
  if not path.is_file():
    return None
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  if not isinstance(data, dict):
    return None
  file_run_id = str(data.get("dispatch_run_id", "")).strip()
  if run_id and file_run_id and file_run_id != run_id:
    return None
  try:
    current = int(data["current_update"])
    total = int(data["total_updates"])
  except (KeyError, TypeError, ValueError):
    return None
  if total < 1:
    return None
  return {
    "current_update": max(0, min(current, total)),
    "total_updates": total,
  }


def total_updates_from_job(job: dict[str, Any]) -> int | None:
  overrides = job.get("overrides") or {}
  raw = overrides.get("num_updates")
  if raw is None:
    return None
  try:
    n = int(raw)
  except (TypeError, ValueError):
    return None
  return n if n >= 1 else None
