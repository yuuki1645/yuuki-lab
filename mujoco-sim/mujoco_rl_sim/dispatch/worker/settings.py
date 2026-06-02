"""Worker 設定（TOML）。"""

from __future__ import annotations

import os
import socket
import tomllib
from dataclasses import dataclass
from pathlib import Path

from mujoco_rl_sim.dispatch.paths import MUJOCO_RL_SIM_ROOT


@dataclass(frozen=True)
class WorkerSettings:
  worker_id: str
  coordinator_url: str
  api_token: str | None
  max_concurrent_jobs: int
  poll_interval_sec: float
  heartbeat_interval_sec: float
  mujoco_rl_sim_root: Path
  artifacts_root: Path | None


def load_worker_settings(config_path: Path) -> WorkerSettings:
  if not config_path.is_file():
    raise FileNotFoundError(f"Worker 設定がありません: {config_path}")
  data = tomllib.loads(config_path.read_text(encoding="utf-8"))

  worker_id = str(data.get("worker_id", "")).strip() or socket.gethostname()
  url = os.environ.get("MUJOCO_DISPATCH_URL", data.get("coordinator_url", "http://127.0.0.1:8790"))
  token = os.environ.get("MUJOCO_DISPATCH_TOKEN", data.get("api_token"))
  if token == "":
    token = None
  max_jobs = int(data.get("max_concurrent_jobs", 1))
  poll = float(data.get("poll_interval_sec", 10.0))
  hb = float(data.get("heartbeat_interval_sec", 15.0))
  root_raw = data.get("mujoco_rl_sim_root", "")
  root = Path(root_raw).resolve() if root_raw else MUJOCO_RL_SIM_ROOT
  art_raw = data.get("artifacts_root", "")
  artifacts = Path(art_raw).resolve() if art_raw else None

  return WorkerSettings(
    worker_id=worker_id,
    coordinator_url=str(url).rstrip("/"),
    api_token=str(token) if token else None,
    max_concurrent_jobs=max(1, max_jobs),
    poll_interval_sec=poll,
    heartbeat_interval_sec=hb,
    mujoco_rl_sim_root=root,
    artifacts_root=artifacts,
  )
