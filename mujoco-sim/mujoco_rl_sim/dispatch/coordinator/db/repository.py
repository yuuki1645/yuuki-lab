"""ジョブ / sweep / worker の永続化。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from mujoco_rl_sim.dispatch.common.job_display import enrich_jobs_display_fields
from mujoco_rl_sim.dispatch.common.models import JobStatus
from mujoco_rl_sim.dispatch.common.primary_metric import PRIMARY_METRIC_NAME
from mujoco_rl_sim.dispatch.common.progress import total_updates_from_job
from mujoco_rl_sim.dispatch.common.sweep_spec import PlannedJob, SweepSpec

_HEARTBEAT_SEC = 15
_LEASE_TIMEOUT_SEC = 90
_WORKER_ONLINE_TIMEOUT_SEC = 45


def _utc_now() -> datetime:
  return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
  return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc_iso(value: str | None) -> datetime | None:
  if not value:
    return None
  raw = value.strip()
  try:
    if raw.endswith("Z"):
      return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(raw).astimezone(timezone.utc)
  except ValueError:
    return None


def _worker_is_online(last_heartbeat_at: str | None, *, now: datetime | None = None) -> bool:
  hb = _parse_utc_iso(last_heartbeat_at)
  if hb is None:
    return False
  ref = now or _utc_now()
  return (ref - hb).total_seconds() <= _WORKER_ONLINE_TIMEOUT_SEC


class DispatchRepository:
  def __init__(self, conn: sqlite3.Connection) -> None:
    self._conn = conn

  def expire_stale_jobs(self) -> int:
    """lease / running の失効ジョブを failed にする。"""
    now = _iso(_utc_now())
    cur = self._conn.cursor()
    cur.execute(
      """
      UPDATE jobs
      SET status = ?, error_message = ?, finished_at = ?, lease_expires_at = NULL
      WHERE status IN (?, ?)
        AND lease_expires_at IS NOT NULL
        AND lease_expires_at < ?
      """,
      (
        JobStatus.FAILED.value,
        "lease/heartbeat timeout",
        now,
        JobStatus.LEASED.value,
        JobStatus.RUNNING.value,
        now,
      ),
    )
    n = cur.rowcount
    self._conn.commit()
    return n

  def register_sweep(self, spec: SweepSpec, *, spec_path: str | None, jobs: list[PlannedJob]) -> int:
    cur = self._conn.cursor()
    cur.execute("SELECT 1 FROM sweeps WHERE sweep_id = ?", (spec.sweep_id,))
    if cur.fetchone():
      raise ValueError(f"sweep_id は既に登録済みです: {spec.sweep_id}")

    cur.execute(
      """
      INSERT INTO sweeps (sweep_id, exp_id, description, shuffle_seed, status, spec_path)
      VALUES (?, ?, ?, ?, 'active', ?)
      """,
      (spec.sweep_id, spec.exp_id, spec.description, spec.shuffle_seed, spec_path),
    )
    inserted = 0
    for job in jobs:
      try:
        cur.execute(
          """
          INSERT INTO jobs (
            run_id, sweep_id, exp_id, config_hash, seed, run_index,
            status, queue_position, overrides_json,
            config_id, seed_id, config_overrides_json
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
            job.run_id,
            job.sweep_id,
            job.exp_id,
            job.config_hash,
            job.seed,
            job.run_index,
            JobStatus.QUEUED.value,
            job.queue_position,
            json.dumps(job.overrides, ensure_ascii=False),
            job.config_id,
            job.seed_id,
            json.dumps(job.config_overrides, ensure_ascii=False),
          ),
        )
        inserted += 1
      except sqlite3.IntegrityError as exc:
        raise ValueError(f"run_id 重複: {job.run_id}") from exc
    self._conn.commit()
    return inserted

  def cancel_sweep(self, sweep_id: str) -> int:
    now = _iso(_utc_now())
    cur = self._conn.cursor()
    cur.execute("UPDATE sweeps SET status = 'cancelled' WHERE sweep_id = ?", (sweep_id,))
    cur.execute(
      """
      UPDATE jobs
      SET status = ?, finished_at = ?
      WHERE sweep_id = ? AND status = ?
      """,
      (JobStatus.CANCELLED.value, now, sweep_id, JobStatus.QUEUED.value),
    )
    n = cur.rowcount
    self._conn.commit()
    return n

  def delete_sweep(self, sweep_id: str) -> dict[str, int]:
    """sweep と配下ジョブを DB から削除する。実行中ジョブがあっても削除する。"""
    cur = self._conn.cursor()
    cur.execute("SELECT 1 FROM sweeps WHERE sweep_id = ?", (sweep_id,))
    if cur.fetchone() is None:
      raise ValueError(f"sweep が見つかりません: {sweep_id}")

    cur.execute(
      """
      SELECT COUNT(*) FROM jobs
      WHERE sweep_id = ? AND status IN (?, ?)
      """,
      (sweep_id, JobStatus.LEASED.value, JobStatus.RUNNING.value),
    )
    active = int(cur.fetchone()[0])

    cur.execute("SELECT COUNT(*) FROM jobs WHERE sweep_id = ?", (sweep_id,))
    job_count = int(cur.fetchone()[0])

    cur.execute("DELETE FROM jobs WHERE sweep_id = ?", (sweep_id,))
    cur.execute("DELETE FROM sweeps WHERE sweep_id = ?", (sweep_id,))
    self._conn.commit()
    return {"deleted_jobs": job_count, "active_jobs_removed": active}

  def upsert_worker(
    self,
    *,
    worker_id: str,
    hostname: str,
    max_concurrent_jobs: int,
    metadata: dict[str, Any] | None = None,
  ) -> None:
    cur = self._conn.cursor()
    cur.execute(
      """
      INSERT INTO workers (worker_id, hostname, max_concurrent_jobs, last_heartbeat_at, metadata_json)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(worker_id) DO UPDATE SET
        hostname = excluded.hostname,
        max_concurrent_jobs = excluded.max_concurrent_jobs,
        last_heartbeat_at = excluded.last_heartbeat_at,
        metadata_json = excluded.metadata_json
      """,
      (
        worker_id,
        hostname,
        max_concurrent_jobs,
        _iso(_utc_now()),
        json.dumps(metadata or {}, ensure_ascii=False),
      ),
    )
    self._conn.commit()

  def worker_heartbeat(self, worker_id: str) -> None:
    cur = self._conn.cursor()
    cur.execute(
      "UPDATE workers SET last_heartbeat_at = ? WHERE worker_id = ?",
      (_iso(_utc_now()), worker_id),
    )
    self._conn.commit()

  def count_worker_active_jobs(self, worker_id: str) -> int:
    cur = self._conn.cursor()
    cur.execute(
      """
      SELECT COUNT(*) FROM jobs
      WHERE worker_id = ? AND status IN (?, ?)
      """,
      (worker_id, JobStatus.LEASED.value, JobStatus.RUNNING.value),
    )
    return int(cur.fetchone()[0])

  def lease_next_job(self, *, worker_id: str) -> dict[str, Any] | None:
    self.expire_stale_jobs()
    cur = self._conn.cursor()
    cur.execute(
      """
      SELECT j.run_id FROM jobs j
      JOIN sweeps s ON s.sweep_id = j.sweep_id
      WHERE j.status = ? AND s.status = 'active'
      ORDER BY j.queue_position ASC
      LIMIT 1
      """,
      (JobStatus.QUEUED.value,),
    )
    row = cur.fetchone()
    if row is None:
      return None
    run_id = row["run_id"]
    expires = _utc_now() + timedelta(seconds=_LEASE_TIMEOUT_SEC)
    cur.execute(
      """
      UPDATE jobs
      SET status = ?, worker_id = ?, lease_expires_at = ?
      WHERE run_id = ? AND status = ?
      """,
      (JobStatus.LEASED.value, worker_id, _iso(expires), run_id, JobStatus.QUEUED.value),
    )
    if cur.rowcount != 1:
      self._conn.commit()
      return None
    self._conn.commit()
    return self.get_job(run_id)

  def mark_running(self, run_id: str, *, worker_id: str) -> bool:
    job = self.get_job(run_id)
    total = total_updates_from_job(job) if job else None
    expires = _utc_now() + timedelta(seconds=_LEASE_TIMEOUT_SEC)
    cur = self._conn.cursor()
    cur.execute(
      """
      UPDATE jobs
      SET status = ?, started_at = COALESCE(started_at, ?), lease_expires_at = ?,
          total_updates = COALESCE(?, total_updates),
          current_update = COALESCE(current_update, 0)
      WHERE run_id = ? AND worker_id = ? AND status = ?
      """,
      (
        JobStatus.RUNNING.value,
        _iso(_utc_now()),
        _iso(expires),
        total,
        run_id,
        worker_id,
        JobStatus.LEASED.value,
      ),
    )
    ok = cur.rowcount == 1
    self._conn.commit()
    return ok

  def refresh_job_lease(
    self,
    run_id: str,
    *,
    worker_id: str,
    current_update: int | None = None,
    total_updates: int | None = None,
  ) -> bool:
    expires = _utc_now() + timedelta(seconds=_LEASE_TIMEOUT_SEC)
    now = _iso(_utc_now())
    cur = self._conn.cursor()
    if current_update is not None or total_updates is not None:
      cur.execute(
        """
        UPDATE jobs
        SET lease_expires_at = ?,
            current_update = CASE
              WHEN ? IS NULL THEN current_update
              ELSE MAX(COALESCE(current_update, 0), ?)
            END,
            total_updates = COALESCE(?, total_updates),
            progress_updated_at = ?
        WHERE run_id = ? AND worker_id = ? AND status IN (?, ?)
        """,
        (
          _iso(expires),
          current_update,
          current_update,
          total_updates,
          now,
          run_id,
          worker_id,
          JobStatus.LEASED.value,
          JobStatus.RUNNING.value,
        ),
      )
    else:
      cur.execute(
        """
        UPDATE jobs SET lease_expires_at = ?
        WHERE run_id = ? AND worker_id = ? AND status IN (?, ?)
        """,
        (
          _iso(expires),
          run_id,
          worker_id,
          JobStatus.LEASED.value,
          JobStatus.RUNNING.value,
        ),
      )
    ok = cur.rowcount == 1
    self._conn.commit()
    return ok

  def complete_job(
    self,
    run_id: str,
    *,
    worker_id: str,
    primary_metric: float | None,
    artifact_path: str | None,
    git_commit: str | None,
  ) -> bool:
    now = _iso(_utc_now())
    cur = self._conn.cursor()
    cur.execute(
      """
      UPDATE jobs
      SET status = ?, finished_at = ?, lease_expires_at = NULL,
          primary_metric = ?, primary_metric_name = ?, artifact_path = ?, git_commit = ?,
          current_update = COALESCE(total_updates, current_update),
          progress_updated_at = ?
      WHERE run_id = ? AND worker_id = ? AND status IN (?, ?)
      """,
      (
        JobStatus.SUCCEEDED.value,
        now,
        primary_metric,
        PRIMARY_METRIC_NAME if primary_metric is not None else None,
        artifact_path,
        git_commit,
        now,
        run_id,
        worker_id,
        JobStatus.LEASED.value,
        JobStatus.RUNNING.value,
      ),
    )
    ok = cur.rowcount == 1
    self._conn.commit()
    return ok

  def fail_job(
    self,
    run_id: str,
    *,
    worker_id: str,
    error_message: str,
  ) -> bool:
    now = _iso(_utc_now())
    cur = self._conn.cursor()
    cur.execute(
      """
      UPDATE jobs
      SET status = ?, finished_at = ?, lease_expires_at = NULL, error_message = ?
      WHERE run_id = ? AND worker_id = ? AND status IN (?, ?, ?)
      """,
      (
        JobStatus.FAILED.value,
        now,
        error_message[:4000],
        run_id,
        worker_id,
        JobStatus.QUEUED.value,
        JobStatus.LEASED.value,
        JobStatus.RUNNING.value,
      ),
    )
    ok = cur.rowcount == 1
    self._conn.commit()
    return ok

  def get_job(self, run_id: str) -> dict[str, Any] | None:
    cur = self._conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    if row is None:
      return None
    job = self._job_row_to_dict(row)
    enrich_jobs_display_fields([job])
    return job

  def list_sweeps(self) -> list[dict[str, Any]]:
    cur = self._conn.cursor()
    cur.execute(
      """
      SELECT s.*,
        SUM(CASE WHEN j.status='queued' THEN 1 ELSE 0 END) AS queued,
        SUM(CASE WHEN j.status IN ('leased','running') THEN 1 ELSE 0 END) AS running,
        SUM(CASE WHEN j.status='succeeded' THEN 1 ELSE 0 END) AS succeeded,
        SUM(CASE WHEN j.status='failed' THEN 1 ELSE 0 END) AS failed,
        SUM(CASE WHEN j.status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
        COUNT(j.run_id) AS job_count
      FROM sweeps s
      LEFT JOIN jobs j ON j.sweep_id = s.sweep_id
      GROUP BY s.sweep_id
      ORDER BY s.created_at DESC
      """
    )
    return [dict(r) for r in cur.fetchall()]

  def list_jobs(
    self,
    *,
    sweep_id: str | None = None,
    status: str | None = None,
    limit: int = 500,
  ) -> list[dict[str, Any]]:
    q = "SELECT * FROM jobs WHERE 1=1"
    params: list[Any] = []
    if sweep_id:
      q += " AND sweep_id = ?"
      params.append(sweep_id)
    if status:
      q += " AND status = ?"
      params.append(status)
    q += " ORDER BY queue_position ASC LIMIT ?"
    params.append(limit)
    cur = self._conn.cursor()
    cur.execute(q, params)
    jobs = [self._job_row_to_dict(r) for r in cur.fetchall()]
    enrich_jobs_display_fields(jobs)
    return jobs

  def list_workers(self) -> list[dict[str, Any]]:
    cur = self._conn.cursor()
    cur.execute(
      """
      SELECT w.*,
        (SELECT COUNT(*) FROM jobs j
         WHERE j.worker_id = w.worker_id AND j.status IN ('leased','running')) AS active_jobs
      FROM workers w
      ORDER BY w.worker_id
      """
    )
    workers = [dict(r) for r in cur.fetchall()]
    now = _utc_now()
    for w in workers:
      w["online"] = _worker_is_online(w.get("last_heartbeat_at"), now=now)
    return workers

  @staticmethod
  def _job_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["overrides"] = json.loads(d.pop("overrides_json"))
    raw_cfg = d.get("config_overrides_json")
    if raw_cfg:
      d["config_overrides"] = json.loads(raw_cfg)
    return d
