"""Worker メインループ（固定並列スロット）。"""

from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from mujoco_rl_sim.dispatch.worker.client import CoordinatorClient
from mujoco_rl_sim.dispatch.worker.executor import run_train_job
from mujoco_rl_sim.dispatch.worker.settings import WorkerSettings


class WorkerAgent:
  def __init__(self, settings: WorkerSettings) -> None:
    self._settings = settings
    self._client = CoordinatorClient(settings.coordinator_url, api_token=settings.api_token)
    self._stop = threading.Event()
    self._active: dict[str, Future[tuple[int, str, float | None, str | None]]] = {}
    self._lock = threading.Lock()

  def run_forever(self) -> None:
    s = self._settings
    self._client.register_worker(
      worker_id=s.worker_id,
      hostname=socket.gethostname(),
      max_concurrent_jobs=s.max_concurrent_jobs,
    )
    print(f"[dispatch-worker] id={s.worker_id} slots={s.max_concurrent_jobs} -> {s.coordinator_url}")

    last_worker_hb = 0.0
    with ThreadPoolExecutor(max_workers=s.max_concurrent_jobs) as pool:
      while not self._stop.is_set():
        now = time.monotonic()
        if now - last_worker_hb >= s.heartbeat_interval_sec:
          try:
            self._client.worker_heartbeat(s.worker_id)
          except RuntimeError as exc:
            print(f"[dispatch-worker] heartbeat error: {exc}")
          last_worker_hb = now

        self._reap_finished()
        self._heartbeat_running_jobs()

        with self._lock:
          free_slots = s.max_concurrent_jobs - len(self._active)

        for _ in range(free_slots):
          try:
            job = self._client.lease_job(s.worker_id)
          except RuntimeError as exc:
            print(f"[dispatch-worker] lease error: {exc}")
            break
          if job is None:
            break
          self._start_job(pool, job)

        time.sleep(s.poll_interval_sec)

  def _start_job(self, pool: ThreadPoolExecutor, job: dict[str, Any]) -> None:
    run_id = job["run_id"]
    try:
      self._client.start_job(run_id, worker_id=self._settings.worker_id)
    except RuntimeError as exc:
      print(f"[dispatch-worker] start failed {run_id}: {exc}")
      try:
        self._client.fail_job(run_id, worker_id=self._settings.worker_id, error_message=str(exc))
      except RuntimeError:
        pass
      return

    print(f"[dispatch-worker] running {run_id} ({job['exp_id']})")
    fut = pool.submit(
      run_train_job,
      job,
      mujoco_rl_sim_root=self._settings.mujoco_rl_sim_root,
    )
    with self._lock:
      self._active[run_id] = fut

  def _heartbeat_running_jobs(self) -> None:
    with self._lock:
      run_ids = list(self._active.keys())
    for run_id in run_ids:
      try:
        self._client.job_heartbeat(run_id, worker_id=self._settings.worker_id)
      except RuntimeError:
        pass

  def _reap_finished(self) -> None:
    with self._lock:
      items = list(self._active.items())
    for run_id, fut in items:
      if not fut.done():
        continue
      try:
        code, log_tail, primary, artifact = fut.result()
      except Exception as exc:
        code = 1
        log_tail = str(exc)
        primary = None
        artifact = None

      if code == 0:
        try:
          self._client.complete_job(
            run_id,
            worker_id=self._settings.worker_id,
            primary_metric=primary,
            artifact_path=artifact,
            git_commit=None,
          )
          print(f"[dispatch-worker] succeeded {run_id} metric={primary}")
        except RuntimeError as exc:
          print(f"[dispatch-worker] complete failed {run_id}: {exc}")
      else:
        try:
          self._client.fail_job(
            run_id,
            worker_id=self._settings.worker_id,
            error_message=log_tail or f"exit {code}",
          )
          print(f"[dispatch-worker] failed {run_id} code={code}")
        except RuntimeError as exc:
          print(f"[dispatch-worker] fail report error {run_id}: {exc}")

      with self._lock:
        self._active.pop(run_id, None)
