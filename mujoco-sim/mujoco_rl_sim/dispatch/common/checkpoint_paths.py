"""runs/ 配下チェックポイントのパス検証と exp 解決。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_EXP_ID_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


@dataclass(frozen=True)
class CheckpointLocation:
  """runs ルートからの相対パスで表す 1 チェックポイント。"""

  checkpoint_rel: str
  exp_id: str
  run_dir: str
  filename: str
  archive: bool


def _validate_exp_id(exp_id: str) -> None:
  if not exp_id or not _EXP_ID_RE.fullmatch(exp_id):
    raise ValueError(f"invalid exp_id: {exp_id!r}")


def parse_checkpoint_rel(checkpoint_rel: str) -> CheckpointLocation:
  """``runs`` ルートからの相対パス（POSIX）を分解する。"""
  rel = checkpoint_rel.strip().replace("\\", "/").lstrip("/")
  if not rel or ".." in rel.split("/"):
    raise ValueError(f"invalid checkpoint_rel: {checkpoint_rel!r}")

  parts = rel.split("/")
  if parts[0] == "archive":
    if len(parts) != 4:
      raise ValueError(f"invalid archive checkpoint_rel: {checkpoint_rel!r}")
    _, exp_id, run_dir, filename = parts
    archive = True
  elif len(parts) == 3:
    exp_id, run_dir, filename = parts
    archive = False
  else:
    raise ValueError(f"invalid checkpoint_rel: {checkpoint_rel!r}")

  _validate_exp_id(exp_id)
  if not filename.endswith(".pt"):
    raise ValueError(f"not a checkpoint file: {filename!r}")

  return CheckpointLocation(
    checkpoint_rel=rel,
    exp_id=exp_id,
    run_dir=run_dir,
    filename=filename,
    archive=archive,
  )


def resolve_checkpoint_file(*, runs_root: Path, checkpoint_rel: str) -> Path:
  """検証済みの絶対パスを返す。"""
  loc = parse_checkpoint_rel(checkpoint_rel)
  runs_root = runs_root.resolve()
  path = (runs_root / loc.checkpoint_rel).resolve()
  try:
    path.relative_to(runs_root)
  except ValueError as exc:
    raise ValueError(f"checkpoint outside runs root: {checkpoint_rel!r}") from exc
  if not path.is_file():
    raise FileNotFoundError(f"checkpoint not found: {path}")
  return path
