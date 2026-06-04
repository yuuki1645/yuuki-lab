"""runs/ 配下の .pt チェックポイント一覧。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mujoco_rl_sim.dispatch.common.checkpoint_paths import parse_checkpoint_rel
from mujoco_rl_sim.dispatch.paths import resolve_experiment_dir

FILTERABLE_CHECKPOINT_FILENAMES = frozenset({"final.pt", "latest.pt"})


def _checkpoint_entry(
  *,
  runs_root: Path,
  rel_posix: str,
  archive: bool,
) -> dict[str, Any] | None:
  try:
    loc = parse_checkpoint_rel(rel_posix)
  except ValueError:
    return None
  if loc.archive != archive:
    return None

  path = runs_root / rel_posix
  if not path.is_file():
    return None

  try:
    resolve_experiment_dir(loc.exp_id, archive=loc.archive)
    experiment_found = True
  except FileNotFoundError:
    experiment_found = False

  exp_path = None
  visualize_py = False
  if experiment_found:
    try:
      exp_path = resolve_experiment_dir(loc.exp_id, archive=loc.archive)
      visualize_py = (exp_path / "visualize.py").is_file()
    except FileNotFoundError:
      experiment_found = False

  stat = path.stat()
  mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

  return {
    "checkpoint_rel": rel_posix,
    "exp_id": loc.exp_id,
    "run_dir": loc.run_dir,
    "filename": loc.filename,
    "archive": loc.archive,
    "size_bytes": stat.st_size,
    "mtime_utc": mtime,
    "experiment_found": experiment_found,
    "visualizable": visualize_py,
  }


def _iter_checkpoint_files(runs_root: Path) -> list[tuple[str, bool]]:
  """(relative posix path, archive flag)"""
  if not runs_root.is_dir():
    return []

  found: list[tuple[str, bool]] = []
  for path in runs_root.rglob("*.pt"):
    if not path.is_file():
      continue
    try:
      rel = path.relative_to(runs_root)
    except ValueError:
      continue
    rel_posix = rel.as_posix()
    parts = rel.parts
    if parts[0] == "archive":
      if len(parts) != 4:
        continue
      found.append((rel_posix, True))
    elif len(parts) == 3:
      found.append((rel_posix, False))
  return found


def list_checkpoints(
  *,
  runs_root: Path,
  exp_id: str | None = None,
  run_dir: str | None = None,
  filename: str | None = None,
  archive: bool | None = None,
  visualizable_only: bool = False,
  limit: int = 500,
  offset: int = 0,
) -> dict[str, Any]:
  """チェックポイント一覧（mtime 降順）。

  ``filename`` に ``final.pt`` または ``latest.pt`` を指定するとそのファイルのみ。
  """
  runs_root = runs_root.resolve()
  limit = max(1, min(limit, 5000))
  offset = max(0, offset)
  if filename is not None and filename not in FILTERABLE_CHECKPOINT_FILENAMES:
    raise ValueError(
      f"filename must be one of {sorted(FILTERABLE_CHECKPOINT_FILENAMES)}: {filename!r}"
    )

  entries: list[dict[str, Any]] = []
  for rel_posix, is_archive in _iter_checkpoint_files(runs_root):
    if archive is not None and is_archive != archive:
      continue
    entry = _checkpoint_entry(
      runs_root=runs_root,
      rel_posix=rel_posix,
      archive=is_archive,
    )
    if entry is None:
      continue
    if exp_id is not None and entry["exp_id"] != exp_id:
      continue
    if run_dir is not None and entry["run_dir"] != run_dir:
      continue
    if filename is not None and entry["filename"] != filename:
      continue
    if visualizable_only and not entry["visualizable"]:
      continue
    entries.append(entry)

  entries.sort(key=lambda e: e["mtime_utc"], reverse=True)
  total = len(entries)
  page = entries[offset : offset + limit]

  exp_ids = sorted({e["exp_id"] for e in entries})
  return {
    "checkpoints": page,
    "total": total,
    "limit": limit,
    "offset": offset,
    "exp_ids": exp_ids,
  }
