"""SQLite 接続。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from mujoco_rl_sim.dispatch.paths import default_db_path

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
  path = db_path or default_db_path()
  path.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(str(path), check_same_thread=False)
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON")
  conn.executescript(_SCHEMA)
  conn.commit()
  return conn
