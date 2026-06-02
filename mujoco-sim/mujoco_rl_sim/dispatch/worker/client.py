"""Coordinator HTTP クライアント。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class CoordinatorClient:
  def __init__(self, base_url: str, *, api_token: str | None = None) -> None:
    self._base = base_url.rstrip("/")
    self._token = api_token

  def _request(
    self,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
  ) -> Any:
    url = f"{self._base}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if self._token:
      headers["X-Dispatch-Token"] = self._token
    if body is not None:
      data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
      with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        if not raw:
          return None
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
      detail = exc.read().decode("utf-8", errors="replace")
      raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc

  def register_worker(
    self,
    *,
    worker_id: str,
    hostname: str,
    max_concurrent_jobs: int,
  ) -> None:
    self._request(
      "POST",
      "/api/workers/register",
      {
        "worker_id": worker_id,
        "hostname": hostname,
        "max_concurrent_jobs": max_concurrent_jobs,
      },
    )

  def worker_heartbeat(self, worker_id: str) -> None:
    self._request("POST", "/api/workers/heartbeat", {"worker_id": worker_id})

  def lease_job(self, worker_id: str) -> dict[str, Any] | None:
    out = self._request("POST", "/api/jobs/lease", {"worker_id": worker_id})
    return out.get("job") if out else None

  def start_job(self, run_id: str, *, worker_id: str) -> None:
    self._request("POST", f"/api/jobs/{run_id}/start", {"worker_id": worker_id})

  def job_heartbeat(
    self,
    run_id: str,
    *,
    worker_id: str,
    current_update: int | None = None,
    total_updates: int | None = None,
  ) -> None:
    body: dict[str, Any] = {"worker_id": worker_id}
    if current_update is not None:
      body["current_update"] = current_update
    if total_updates is not None:
      body["total_updates"] = total_updates
    self._request("POST", f"/api/jobs/{run_id}/heartbeat", body)

  def complete_job(
    self,
    run_id: str,
    *,
    worker_id: str,
    primary_metric: float | None = None,
    artifact_path: str | None = None,
    git_commit: str | None = None,
  ) -> None:
    self._request(
      "POST",
      f"/api/jobs/{run_id}/complete",
      {
        "worker_id": worker_id,
        "primary_metric": primary_metric,
        "artifact_path": artifact_path,
        "git_commit": git_commit,
      },
    )

  def fail_job(self, run_id: str, *, worker_id: str, error_message: str) -> None:
    self._request(
      "POST",
      f"/api/jobs/{run_id}/fail",
      {"worker_id": worker_id, "error_message": error_message},
    )
