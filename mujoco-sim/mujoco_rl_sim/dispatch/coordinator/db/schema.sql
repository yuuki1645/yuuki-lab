-- Coordinator SQLite schema (v0)

CREATE TABLE IF NOT EXISTS sweeps (
  sweep_id TEXT PRIMARY KEY,
  exp_id TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  shuffle_seed INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  spec_path TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
  run_id TEXT PRIMARY KEY,
  sweep_id TEXT NOT NULL REFERENCES sweeps(sweep_id),
  exp_id TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  seed INTEGER NOT NULL,
  run_index INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  queue_position INTEGER NOT NULL,
  worker_id TEXT,
  overrides_json TEXT NOT NULL,
  primary_metric REAL,
  primary_metric_name TEXT,
  error_message TEXT,
  artifact_path TEXT,
  git_commit TEXT,
  lease_expires_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  started_at TEXT,
  finished_at TEXT,
  current_update INTEGER,
  total_updates INTEGER,
  progress_updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_sweep_status ON jobs(sweep_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_status_queue ON jobs(status, queue_position);

CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT PRIMARY KEY,
  hostname TEXT NOT NULL,
  max_concurrent_jobs INTEGER NOT NULL DEFAULT 1,
  last_heartbeat_at TEXT,
  registered_at TEXT NOT NULL DEFAULT (datetime('now')),
  metadata_json TEXT
);
