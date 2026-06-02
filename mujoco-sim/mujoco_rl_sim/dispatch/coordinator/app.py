"""Flask: REST API + 静的 Web UI。"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Flask, jsonify, request, send_from_directory

from mujoco_rl_sim.dispatch.common.auth import check_token
from mujoco_rl_sim.dispatch.coordinator.db.connection import connect
from mujoco_rl_sim.dispatch.coordinator.db.repository import DispatchRepository
from mujoco_rl_sim.dispatch.coordinator.settings import CoordinatorSettings


def create_app(settings: CoordinatorSettings) -> Flask:
  # 既定の /static/（存在しない coordinator/static/）より先に UI 用静的ファイルを配信する
  app = Flask(__name__, static_folder=None)
  conn = connect(settings.db_path)
  repo = DispatchRepository(conn)

  def _auth(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
      if not check_token(request, settings.api_token):
        return jsonify({"error": "unauthorized"}), 401
      return f(*args, **kwargs)

    return wrapper

  @app.get("/health")
  def health() -> Any:
    return jsonify({"ok": True})

  @app.get("/")
  def index() -> Any:
    return send_from_directory(settings.web_root, "index.html")

  @app.get("/static/<path:filename>")
  def static_files(filename: str) -> Any:
    return send_from_directory(settings.web_root, filename)

  @app.get("/api/sweeps")
  @_auth
  def list_sweeps() -> Any:
    return jsonify({"sweeps": repo.list_sweeps()})

  @app.get("/api/sweeps/<sweep_id>")
  @_auth
  def get_sweep(sweep_id: str) -> Any:
    sweeps = [s for s in repo.list_sweeps() if s["sweep_id"] == sweep_id]
    if not sweeps:
      return jsonify({"error": "not found"}), 404
    jobs = repo.list_jobs(sweep_id=sweep_id, limit=10_000)
    return jsonify({"sweep": sweeps[0], "jobs": jobs})

  @app.post("/api/sweeps/<sweep_id>/cancel")
  @_auth
  def cancel_sweep(sweep_id: str) -> Any:
    n = repo.cancel_sweep(sweep_id)
    return jsonify({"cancelled_queued_jobs": n})

  @app.delete("/api/sweeps/<sweep_id>")
  @_auth
  def delete_sweep(sweep_id: str) -> Any:
    try:
      result = repo.delete_sweep(sweep_id)
    except ValueError as exc:
      return jsonify({"error": str(exc)}), 404
    return jsonify({"sweep_id": sweep_id, **result})

  @app.get("/api/jobs")
  @_auth
  def list_jobs() -> Any:
    sweep_id = request.args.get("sweep_id")
    status = request.args.get("status")
    return jsonify({"jobs": repo.list_jobs(sweep_id=sweep_id, status=status)})

  @app.get("/api/jobs/<run_id>")
  @_auth
  def get_job(run_id: str) -> Any:
    job = repo.get_job(run_id)
    if job is None:
      return jsonify({"error": "not found"}), 404
    return jsonify({"job": job})

  @app.post("/api/workers/register")
  @_auth
  def register_worker() -> Any:
    body = request.get_json(force=True, silent=True) or {}
    worker_id = str(body.get("worker_id", "")).strip()
    hostname = str(body.get("hostname", "")).strip()
    max_jobs = int(body.get("max_concurrent_jobs", 1))
    if not worker_id:
      return jsonify({"error": "worker_id required"}), 400
    repo.upsert_worker(
      worker_id=worker_id,
      hostname=hostname or worker_id,
      max_concurrent_jobs=max(1, max_jobs),
      metadata=body.get("metadata"),
    )
    return jsonify({"ok": True, "worker_id": worker_id})

  @app.post("/api/workers/heartbeat")
  @_auth
  def worker_hb() -> Any:
    body = request.get_json(force=True, silent=True) or {}
    worker_id = str(body.get("worker_id", "")).strip()
    if not worker_id:
      return jsonify({"error": "worker_id required"}), 400
    repo.worker_heartbeat(worker_id)
    return jsonify({"ok": True})

  @app.get("/api/workers")
  @_auth
  def list_workers() -> Any:
    return jsonify({"workers": repo.list_workers()})

  @app.post("/api/jobs/lease")
  @_auth
  def lease_job() -> Any:
    body = request.get_json(force=True, silent=True) or {}
    worker_id = str(body.get("worker_id", "")).strip()
    if not worker_id:
      return jsonify({"error": "worker_id required"}), 400
    job = repo.lease_next_job(worker_id=worker_id)
    if job is None:
      return jsonify({"job": None})
    return jsonify({"job": job})

  @app.post("/api/jobs/<run_id>/start")
  @_auth
  def start_job(run_id: str) -> Any:
    body = request.get_json(force=True, silent=True) or {}
    worker_id = str(body.get("worker_id", "")).strip()
    if not repo.mark_running(run_id, worker_id=worker_id):
      return jsonify({"error": "cannot start"}), 409
    return jsonify({"ok": True})

  @app.post("/api/jobs/<run_id>/heartbeat")
  @_auth
  def job_hb(run_id: str) -> Any:
    body = request.get_json(force=True, silent=True) or {}
    worker_id = str(body.get("worker_id", "")).strip()
    if not repo.refresh_job_lease(run_id, worker_id=worker_id):
      return jsonify({"error": "cannot refresh lease"}), 409
    return jsonify({"ok": True})

  @app.post("/api/jobs/<run_id>/complete")
  @_auth
  def complete_job(run_id: str) -> Any:
    body = request.get_json(force=True, silent=True) or {}
    worker_id = str(body.get("worker_id", "")).strip()
    ok = repo.complete_job(
      run_id,
      worker_id=worker_id,
      primary_metric=body.get("primary_metric"),
      artifact_path=body.get("artifact_path"),
      git_commit=body.get("git_commit"),
    )
    if not ok:
      return jsonify({"error": "cannot complete"}), 409
    return jsonify({"ok": True})

  @app.post("/api/jobs/<run_id>/fail")
  @_auth
  def fail_job(run_id: str) -> Any:
    body = request.get_json(force=True, silent=True) or {}
    worker_id = str(body.get("worker_id", "")).strip()
    msg = str(body.get("error_message", "failed"))
    ok = repo.fail_job(run_id, worker_id=worker_id, error_message=msg)
    if not ok:
      return jsonify({"error": "cannot fail"}), 409
    return jsonify({"ok": True})

  @app.get("/api/ui/dashboard")
  @_auth
  def dashboard() -> Any:
    repo.expire_stale_jobs()
    return jsonify(
      {
        "sweeps": repo.list_sweeps(),
        "workers": repo.list_workers(),
        "recent_jobs": repo.list_jobs(limit=100),
      }
    )

  return app
