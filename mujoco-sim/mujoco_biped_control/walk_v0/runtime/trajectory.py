"""軌道・サマリの書き出し。"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable


TRAJECTORY_FIELDS = [
  "step",
  "time_s",
  "imu_x",
  "imu_dx",
  "upright",
  "left_foot_on_floor",
  "right_foot_on_floor",
  "single_support",
  "aerial_steps",
  "reward_total",
  "termination_reason",
  * [f"action_{i}" for i in range(12)],
  * [f"ctrl_{k}" for k in ("phase", "swing_left", "wave")],
]


class TrajectoryLogger:
  def __init__(self, run_dir: Path):
    self._run_dir = run_dir
    self._rows: list[dict[str, Any]] = []
    self._jsonl_path = run_dir / "trajectory.jsonl"
    self._jsonl_file = self._jsonl_path.open("w", encoding="utf-8")

  def close(self) -> None:
    if not self._jsonl_file.closed:
      self._jsonl_file.close()

  def log_step(self, row: dict[str, Any]) -> None:
    self._rows.append(row)
    self._jsonl_file.write(json.dumps(row, ensure_ascii=False) + "\n")

  def write_csv(self) -> Path:
    path = self._run_dir / "trajectory.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
      writer = csv.DictWriter(f, fieldnames=TRAJECTORY_FIELDS, extrasaction="ignore")
      writer.writeheader()
      for row in self._rows:
        writer.writerow({k: row.get(k, "") for k in TRAJECTORY_FIELDS})
    return path


def write_json(path: Path, data: Any) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)


def write_manifest(
  run_dir: Path,
  *,
  seed: int,
  run_cfg_path: str,
  controller_cfg_path: str,
  exp030_dir: str,
) -> Path:
  manifest = {
    "seed": seed,
    "run_config": run_cfg_path,
    "controller_config": controller_cfg_path,
    "exp030_dir": exp030_dir,
    "reproduce_hint": (
      "同一 seed で python run.py --config conf/default.yaml を再実行。"
      "インシデント瞬間は replay_incident.py --run-dir <this> --incident-index N"
    ),
  }
  path = run_dir / "run_manifest.json"
  write_json(path, manifest)
  return path
