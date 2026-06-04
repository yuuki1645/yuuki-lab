"""Coordinator 上で visualize.py を subprocess 起動（複数同時可）。"""

from __future__ import annotations

import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mujoco_rl_sim.dispatch.common.checkpoint_paths import (
  parse_checkpoint_rel,
  resolve_checkpoint_file,
)
from mujoco_rl_sim.dispatch.paths import resolve_experiment_dir


@dataclass
class _Session:
  session_id: str
  exp_id: str
  checkpoint_rel: str
  archive: bool
  pid: int
  started_at_utc: str
  process: subprocess.Popen[bytes]


@dataclass
class VisualizeRunner:
  runs_root: Path
  python_executable: str = field(default_factory=lambda: sys.executable)
  log_dir: Path | None = None
  _sessions: dict[str, _Session] = field(default_factory=dict)

  def _prune_finished(self) -> None:
    dead = [sid for sid, s in self._sessions.items() if s.process.poll() is not None]
    for sid in dead:
      del self._sessions[sid]

  def build_command(self, *, exp_path: Path, checkpoint_abs: Path) -> list[str]:
    return [
      self.python_executable,
      "visualize.py",
      "--checkpoint",
      str(checkpoint_abs),
      "--stochastic",
    ]

  def start(self, *, checkpoint_rel: str) -> dict[str, Any]:
    loc = parse_checkpoint_rel(checkpoint_rel)
    checkpoint_abs = resolve_checkpoint_file(
      runs_root=self.runs_root,
      checkpoint_rel=checkpoint_rel,
    )
    exp_path = resolve_experiment_dir(loc.exp_id, archive=loc.archive)
    viz_script = exp_path / "visualize.py"
    if not viz_script.is_file():
      raise FileNotFoundError(f"visualize.py not found: {viz_script}")

    cmd = self.build_command(exp_path=exp_path, checkpoint_abs=checkpoint_abs)
    stdout_dest = subprocess.DEVNULL
    stderr_dest = subprocess.DEVNULL
    log_path: Path | None = None
    if self.log_dir is not None:
      self.log_dir.mkdir(parents=True, exist_ok=True)
      stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
      log_path = self.log_dir / f"visualize_{loc.exp_id}_{stamp}_{uuid.uuid4().hex[:8]}.log"
      stderr_dest = log_path.open("w", encoding="utf-8")

    try:
      proc = subprocess.Popen(
        cmd,
        cwd=exp_path,
        stdout=stdout_dest,
        stderr=stderr_dest,
      )
    except OSError as exc:
      if log_path is not None and hasattr(stderr_dest, "close"):
        stderr_dest.close()
      raise OSError(f"failed to start visualize: {exc}") from exc

    session_id = uuid.uuid4().hex
    started = datetime.now(timezone.utc).isoformat()
    self._sessions[session_id] = _Session(
      session_id=session_id,
      exp_id=loc.exp_id,
      checkpoint_rel=loc.checkpoint_rel,
      archive=loc.archive,
      pid=proc.pid,
      started_at_utc=started,
      process=proc,
    )
    return {
      "session_id": session_id,
      "pid": proc.pid,
      "exp_id": loc.exp_id,
      "checkpoint_rel": loc.checkpoint_rel,
      "archive": loc.archive,
      "started_at_utc": started,
      "log_path": str(log_path) if log_path else None,
      "command": cmd,
    }

  def list_sessions(self) -> list[dict[str, Any]]:
    self._prune_finished()
    return [
      {
        "session_id": s.session_id,
        "pid": s.pid,
        "exp_id": s.exp_id,
        "checkpoint_rel": s.checkpoint_rel,
        "archive": s.archive,
        "started_at_utc": s.started_at_utc,
        "running": s.process.poll() is None,
      }
      for s in self._sessions.values()
    ]
