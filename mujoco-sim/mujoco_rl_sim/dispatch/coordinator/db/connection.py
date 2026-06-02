"""SQLite 接続。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from mujoco_rl_sim.dispatch.paths import default_db_path

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")

_JOB_PROGRESS_COLUMNS: tuple[tuple[str, str], ...] = (
  ("current_update", "INTEGER"),
  ("total_updates", "INTEGER"),
  ("progress_updated_at", "TEXT"),
)

_JOB_DISPLAY_COLUMNS: tuple[tuple[str, str], ...] = (
  ("config_id", "INTEGER"),
  ("seed_id", "INTEGER"),
  ("config_overrides_json", "TEXT"),
)


def _migrate_jobs_columns(conn: sqlite3.Connection, columns: tuple[tuple[str, str], ...]) -> None:
  cur = conn.execute("PRAGMA table_info(jobs)")
  existing = {str(row[1]) for row in cur.fetchall()}
  for name, col_type in columns:
    if name not in existing:
      conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {col_type}")


def _migrate_jobs(conn: sqlite3.Connection) -> None:
  _migrate_jobs_columns(conn, _JOB_PROGRESS_COLUMNS)
  _migrate_jobs_columns(conn, _JOB_DISPLAY_COLUMNS)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
  path = db_path or default_db_path()
  path.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(str(path), check_same_thread=False)
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON")
  conn.executescript(_SCHEMA)
  _migrate_jobs(conn)
  conn.commit()
  return conn
