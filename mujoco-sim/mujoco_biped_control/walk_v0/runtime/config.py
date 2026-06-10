"""walk_v0 設定読み込み。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from walk_meta import EXP030_DIR, EXP_DIR


@dataclass(frozen=True)
class IncidentConfig:
  enabled: bool = True
  min_upright: float = 0.55
  min_imu_z: float = 0.35
  max_aerial_steps: float = 40.0
  min_forward_dx_per_step: float = -0.08
  record_cooldown_steps: int = 25


@dataclass(frozen=True)
class RunConfig:
  seed: int
  max_steps: int
  exp030_dir: Path
  controller_config: Path
  log_every: int
  save_trajectory_csv: bool
  save_trajectory_jsonl: bool
  save_step_snapshots_on_incident: bool
  incident: IncidentConfig


@dataclass(frozen=True)
class ControlParams:
  """controller/walk.py が参照する tunable パラメータ。"""

  cycle_period_s: float = 1.2
  phase_offset: float = 0.0
  swing_hip_pitch: float = 0.25
  swing_knee: float = 0.35
  swing_ankle_pitch: float = 0.15
  stance_hip_pitch: float = -0.05
  stance_knee: float = 0.05
  torso_balance_gain: float = 0.12
  torso_roll_damp: float = 0.05

  @classmethod
  def from_mapping(cls, data: dict[str, Any]) -> ControlParams:
    known = {f.name for f in cls.__dataclass_fields__.values()}
    return cls(**{k: v for k, v in data.items() if k in known})


def _load_yaml(path: Path) -> dict[str, Any]:
  with path.open(encoding="utf-8") as f:
    return yaml.safe_load(f) or {}


def load_run_config(path: Path | None = None) -> RunConfig:
  cfg_path = path or (EXP_DIR / "conf" / "default.yaml")
  raw = _load_yaml(cfg_path)
  inc_raw = raw.get("incident") or {}
  exp030 = raw.get("exp030_dir")
  exp030_path = Path(exp030) if exp030 else EXP030_DIR
  if not exp030_path.is_absolute():
    exp030_path = (EXP_DIR / exp030_path).resolve()

  ctrl_rel = raw.get("controller_config", "conf/controller.yaml")
  ctrl_path = Path(ctrl_rel)
  if not ctrl_path.is_absolute():
    ctrl_path = (EXP_DIR / ctrl_path).resolve()

  return RunConfig(
    seed=int(raw.get("seed", 42)),
    max_steps=int(raw.get("max_steps", 1500)),
    exp030_dir=exp030_path,
    controller_config=ctrl_path,
    log_every=int(raw.get("log_every", 1)),
    save_trajectory_csv=bool(raw.get("save_trajectory_csv", True)),
    save_trajectory_jsonl=bool(raw.get("save_trajectory_jsonl", True)),
    save_step_snapshots_on_incident=bool(
      raw.get("save_step_snapshots_on_incident", True)
    ),
    incident=IncidentConfig(
      enabled=bool(inc_raw.get("enabled", True)),
      min_upright=float(inc_raw.get("min_upright", 0.55)),
      min_imu_z=float(inc_raw.get("min_imu_z", 0.35)),
      max_aerial_steps=float(inc_raw.get("max_aerial_steps", 40)),
      min_forward_dx_per_step=float(
        inc_raw.get("min_forward_dx_per_step", -0.08)
      ),
      record_cooldown_steps=int(inc_raw.get("record_cooldown_steps", 25)),
    ),
  )


def load_control_params(path: Path | None = None) -> ControlParams:
  run_cfg = load_run_config()
  p = path or run_cfg.controller_config
  return ControlParams.from_mapping(_load_yaml(p))
