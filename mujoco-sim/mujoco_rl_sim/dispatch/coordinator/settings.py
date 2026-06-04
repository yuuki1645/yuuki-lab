"""Coordinator 設定（TOML / 環境変数）。"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from mujoco_rl_sim.dispatch.paths import RUNS_ROOT, default_db_path, dispatch_data_dir


@dataclass(frozen=True)
class CoordinatorSettings:
  host: str
  port: int
  db_path: Path
  api_token: str | None
  web_root: Path
  runs_root: Path
  visualize_enabled: bool
  python_executable: str
  visualize_log_dir: Path | None


def load_coordinator_settings(config_path: Path | None = None) -> CoordinatorSettings:
  data: dict = {}
  if config_path and config_path.is_file():
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

  host = os.environ.get("MUJOCO_DISPATCH_HOST", data.get("host", "0.0.0.0"))
  port = int(os.environ.get("MUJOCO_DISPATCH_PORT", data.get("port", 8790)))
  db_raw = os.environ.get("MUJOCO_DISPATCH_DB", data.get("db_path", ""))
  db_path = Path(db_raw).expanduser() if db_raw else default_db_path()
  token = os.environ.get("MUJOCO_DISPATCH_TOKEN", data.get("api_token"))
  if token == "":
    token = None

  web_default = Path(__file__).resolve().parent.parent / "web" / "static"
  web_raw = data.get("web_root", "")
  web_root = Path(web_raw) if web_raw else web_default

  runs_raw = os.environ.get("MUJOCO_DISPATCH_RUNS_ROOT", data.get("runs_root", ""))
  runs_root = Path(runs_raw).expanduser() if runs_raw else RUNS_ROOT

  viz_enabled_raw = os.environ.get(
    "MUJOCO_DISPATCH_VISUALIZE_ENABLED",
    data.get("visualize_enabled", True),
  )
  visualize_enabled = str(viz_enabled_raw).lower() not in ("0", "false", "no")

  python_raw = os.environ.get(
    "MUJOCO_DISPATCH_PYTHON",
    data.get("python_executable", ""),
  )
  python_executable = python_raw.strip() if python_raw else sys.executable

  log_raw = data.get("visualize_log_dir", "")
  if log_raw == "":
    visualize_log_dir: Path | None = dispatch_data_dir() / "visualize_logs"
  elif log_raw is None:
    visualize_log_dir = None
  else:
    visualize_log_dir = Path(log_raw).expanduser()

  return CoordinatorSettings(
    host=str(host),
    port=port,
    db_path=db_path,
    api_token=str(token) if token else None,
    web_root=web_root,
    runs_root=runs_root,
    visualize_enabled=visualize_enabled,
    python_executable=python_executable,
    visualize_log_dir=visualize_log_dir,
  )
