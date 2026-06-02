"""sweep YAML の読込とジョブ展開。"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config_hash import compute_config_hash
from .run_id import build_run_id


@dataclass(frozen=True)
class SweepSpec:
  sweep_id: str
  exp_id: str
  description: str
  shuffle_seed: int
  seeds: tuple[int, ...]
  param_grid: dict[str, list[Any]]
  fixed_overrides: dict[str, Any]


@dataclass(frozen=True)
class PlannedJob:
  run_id: str
  sweep_id: str
  exp_id: str
  config_hash: str
  seed: int
  run_index: int
  overrides: dict[str, Any]
  queue_position: int


def load_sweep_spec(path: Path) -> SweepSpec:
  raw = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(raw, dict):
    raise ValueError(f"sweep YAML は mapping である必要があります: {path}")

  sweep_id = str(raw["sweep_id"]).strip()
  exp_id = str(raw["exp_id"]).strip()
  description = str(raw.get("description", "")).strip()
  shuffle_seed = int(raw.get("shuffle_seed", 0))

  if "seeds" in raw:
    seeds = tuple(int(s) for s in raw["seeds"])
  elif "seed_count" in raw:
    start = int(raw.get("seed_start", 1))
    count = int(raw["seed_count"])
    seeds = tuple(range(start, start + count))
  else:
    raise ValueError("seeds または seed_count が必要です")

  param_grid = raw.get("param_grid") or {}
  if not isinstance(param_grid, dict):
    raise ValueError("param_grid は mapping")
  grid: dict[str, list[Any]] = {}
  for k, v in param_grid.items():
    if isinstance(v, list):
      grid[str(k)] = list(v)
    else:
      grid[str(k)] = [v]

  fixed = dict(raw.get("fixed_overrides") or {})
  return SweepSpec(
    sweep_id=sweep_id,
    exp_id=exp_id,
    description=description,
    shuffle_seed=shuffle_seed,
    seeds=seeds,
    param_grid=grid,
    fixed_overrides=fixed,
  )


def _expand_param_combos(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
  if not grid:
    return [{}]
  keys = sorted(grid.keys())
  values = [grid[k] for k in keys]
  combos: list[dict[str, Any]] = []
  for tup in itertools.product(*values):
    combos.append(dict(zip(keys, tup, strict=True)))
  return combos


def expand_sweep_jobs(spec: SweepSpec) -> list[PlannedJob]:
  """param_grid × seeds のジョブを生成し、shuffle_seed でシャッフルする。"""
  combos = _expand_param_combos(spec.param_grid)
  planned: list[PlannedJob] = []
  run_index = 0
  for combo in combos:
    merged_base = {**spec.fixed_overrides, **combo}
    cfg_hash = compute_config_hash(combo if combo else spec.fixed_overrides)
    for seed in spec.seeds:
      overrides = {**merged_base, "seed": seed}
      run_id = build_run_id(sweep_id=spec.sweep_id, seed=seed, run_index=run_index)
      planned.append(
        PlannedJob(
          run_id=run_id,
          sweep_id=spec.sweep_id,
          exp_id=spec.exp_id,
          config_hash=cfg_hash,
          seed=seed,
          run_index=run_index,
          overrides=overrides,
          queue_position=0,
        )
      )
      run_index += 1

  rng = random.Random(spec.shuffle_seed)
  rng.shuffle(planned)
  return [
    PlannedJob(
      run_id=j.run_id,
      sweep_id=j.sweep_id,
      exp_id=j.exp_id,
      config_hash=j.config_hash,
      seed=j.seed,
      run_index=j.run_index,
      overrides=j.overrides,
      queue_position=i,
    )
    for i, j in enumerate(planned)
  ]
