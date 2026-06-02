"""Coordinator 設定（TOML / 環境変数）。"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from mujoco_rl_sim.dispatch.paths import default_db_path


@dataclass(frozen=True)
class CoordinatorSettings:
  host: str
  port: int
  db_path: Path
  api_token: str | None
  web_root: Path


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

  return CoordinatorSettings(
    host=str(host),
    port=port,
    db_path=db_path,
    api_token=str(token) if token else None,
    web_root=web_root,
  )
