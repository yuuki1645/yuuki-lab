"""eval_report.json の生成。"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from eval.metrics import EpisodeEvalRecord, episode_to_dict, summarize_episodes
from eval.spec import (
  EPISODES_PER_SEED,
  EVAL_SEEDS,
  EVAL_SPEC_ID,
  PRIMARY_METRIC_NAME,
)
from package_meta import EXP_NAME, MUJOCO_RL_SIM_ROOT

_REPORT_SCHEMA_VERSION = 1


def _git_commit() -> str | None:
  try:
    out = subprocess.run(
      ["git", "rev-parse", "HEAD"],
      cwd=MUJOCO_RL_SIM_ROOT.parent,
      capture_output=True,
      text=True,
      check=True,
      timeout=10,
    )
    return out.stdout.strip() or None
  except (OSError, subprocess.CalledProcessError):
    return None


def build_eval_report(
  *,
  checkpoint_path: Path,
  records: list[EpisodeEvalRecord],
  eval_seeds: tuple[int, ...] = EVAL_SEEDS,
  episodes_per_seed: int = EPISODES_PER_SEED,
) -> dict[str, Any]:
  """eval_report.json 用 dict を組み立てる。"""
  summary = summarize_episodes(records)
  return {
    "schema_version": _REPORT_SCHEMA_VERSION,
    "eval_spec_id": EVAL_SPEC_ID,
    "exp_name": EXP_NAME,
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "git_commit": _git_commit(),
    "checkpoint": str(checkpoint_path.resolve()),
    "policy": "act_eval",
    "warmup_enabled": bool(config.WARMUP_ENABLED),
    "max_steps_per_episode": int(config.MAX_STEPS_PER_EPISODE),
    "eval_seeds": list(eval_seeds),
    "episodes_per_seed": int(episodes_per_seed),
    "total_trials": len(records),
    "primary_metric_name": PRIMARY_METRIC_NAME,
    "primary_metric_value": summary["primary_metric_value"],
    "noise_spec": {
      "root_xy_position": False,
      "root_yaw_deg": 3.0,
      "joint_deg": 2.0,
      "root_lin_vel_m_s": 0.05,
      "root_ang_vel_rad_s": 0.1,
    },
    "summary": summary,
    "episodes": [episode_to_dict(r) for r in records],
  }


def write_eval_report(path: Path, report: dict[str, Any]) -> Path:
  """JSON を書き出す。"""
  path = path.resolve()
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8",
  )
  return path
