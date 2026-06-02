"""ドメインモデル（DB行の論理表現）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
  QUEUED = "queued"
  LEASED = "leased"
  RUNNING = "running"
  SUCCEEDED = "succeeded"
  FAILED = "failed"
  CANCELLED = "cancelled"


@dataclass(frozen=True)
class SweepRecord:
  sweep_id: str
  exp_id: str
  description: str
  shuffle_seed: int
  status: str
  job_count: int
  queued: int
  running: int
  succeeded: int
  failed: int
  cancelled: int


@dataclass(frozen=True)
class JobRecord:
  run_id: str
  sweep_id: str
  exp_id: str
  config_hash: str
  seed: int
  run_index: int
  status: JobStatus
  queue_position: int
  worker_id: str | None
  overrides: dict[str, Any]
  primary_metric: float | None
  primary_metric_name: str | None
  error_message: str | None
  artifact_path: str | None
  git_commit: str | None


@dataclass(frozen=True)
class WorkerRecord:
  worker_id: str
  hostname: str
  max_concurrent_jobs: int
  active_jobs: int
  last_heartbeat_at: str | None
