"""Job 一覧向け config_id / seed_id の補完。"""

from __future__ import annotations

import json
from typing import Any


def config_overrides_without_seed(overrides: dict[str, Any]) -> dict[str, Any]:
  return {k: v for k, v in overrides.items() if k != "seed"}


def enrich_jobs_display_fields(jobs: list[dict[str, Any]]) -> None:
  """config_overrides を補完し、未登録の legacy ジョブに表示用 ID を付与する。"""
  for job in jobs:
    if job.get("config_overrides") is None:
      raw = job.get("config_overrides_json")
      if raw:
        job["config_overrides"] = json.loads(raw)
      else:
        job["config_overrides"] = config_overrides_without_seed(job.get("overrides") or {})
    job.pop("config_overrides_json", None)

  legacy = [job for job in jobs if job.get("config_id") is None]
  if not legacy:
    return

  by_sweep: dict[str, dict[str, list[dict[str, Any]]]] = {}
  for job in legacy:
    sweep_id = str(job["sweep_id"])
    cfg_hash = str(job["config_hash"])
    by_sweep.setdefault(sweep_id, {}).setdefault(cfg_hash, []).append(job)

  for groups in by_sweep.values():
    def group_sort_key(cfg_hash: str) -> str:
      sample = groups[cfg_hash][0]
      return json.dumps(sample.get("config_overrides") or {}, sort_keys=True, ensure_ascii=False)

    for config_id, cfg_hash in enumerate(sorted(groups.keys(), key=group_sort_key), start=1):
      group = sorted(groups[cfg_hash], key=lambda j: (int(j["seed"]), int(j["run_index"])))
      shared = group[0].get("config_overrides") or config_overrides_without_seed(group[0].get("overrides") or {})
      for seed_id, job in enumerate(group, start=1):
        job["config_id"] = config_id
        job["seed_id"] = seed_id
        if not job.get("config_overrides"):
          job["config_overrides"] = shared
