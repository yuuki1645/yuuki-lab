"""walk_v0 設定読み込み。"""

from __future__ import annotations

from dataclasses import dataclass
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

  # 周期
  cycle_period_s: float = 1.20
  double_support_s: float = 0.06

  # ベース姿勢（action オフセット、0=stand）
  base_hip_pitch: float = -0.34
  base_knee: float = 0.05
  base_ankle_pitch: float = -0.12
  base_torso_pitch: float = 0.14

  # 支持脚（片足支持時）
  stance_hip_delta: float = -0.03
  stance_knee_delta: float = -0.02
  stance_ankle_delta: float = -0.08
  stance_roll: float = 0.06

  # 蹴り出し（遊脚位相の序盤）
  push_off_hip: float = 0.05
  push_off_knee: float = -0.03
  push_off_ankle: float = -0.14
  push_off_frac: float = 0.25

  # 遊脚軌道
  swing_lift_hip: float = 0.04
  swing_reach_hip: float = -0.12
  swing_knee_amp: float = 0.18
  swing_ankle_lift: float = 0.06
  swing_roll_scale: float = 0.65
  swing_torso_bias: float = 0.03

  # 足先位置補正（未使用・YAML 互換）
  step_length_target: float = 0.12
  foot_place_gain: float = 0.35

  # 直立に応じた遊脚スケール
  upright_swing_min: float = 0.50
  upright_swing_floor: float = 0.45

  # IMU バランス層（支持脚 + 体幹）
  balance_ankle_gain: float = 1.0
  balance_gyro_damp: float = 0.06
  balance_ankle_clip: float = 0.16
  balance_torso_tilt_gain: float = 0.6
  balance_upright_gain: float = 0.4
  balance_upright_target: float = 0.62
  balance_torso_clip: float = 0.12
  balance_height_gain: float = 0.15
  balance_height_clip: float = 0.10
  balance_hip_follow: float = 0.30
  balance_imu_z_target: float = 0.34
  balance_imu_z_gain: float = 2.5

  # 長距離歩行：低 upright 時に歩幅を縮小
  survival_recovery_enabled: bool = True
  survival_upright_thresh: float = 0.56
  survival_upright_floor: float = 0.48
  survival_hip_scale_min: float = 0.55
  survival_torso_gain: float = 0.30

  # upright 急落前に短時間 DS 姿勢を保持
  emergency_ds_enabled: bool = True
  emergency_upright_thresh: float = 0.54
  emergency_hold_steps: int = 10
  emergency_torso_extra: float = 0.10
  balance_tilt_deadband: float = 0.0
  balance_upright_activate: float = 0.0

  # 閉ループ前進（torso のみ・弱め）
  target_dx_per_step: float = 0.0045
  forward_dx_gain: float = 5.0
  torso_balance_gain: float = 0.04
  torso_roll_damp: float = 0.08

  # 旧互換（未使用）
  upright_torso_thresh: float = 0.72
  upright_torso_gain: float = 0.0

  # 旧キー（YAML 互換・未使用）
  swing_duration_s: float = 0.50
  landing_subphase_min: float = 0.55
  stance_hip_pitch: float = -0.34
  stance_knee: float = 0.05
  stance_ankle_pitch: float = -0.12
  stance_hip_roll: float = 0.06
  ds_hip_pitch: float = -0.34
  swing_hip_pitch: float = 0.04
  swing_knee_peak: float = 0.20
  swing_hip_roll: float = 0.06
  push_off_hip_pitch: float = 0.05
  push_off_knee: float = -0.03
  push_off_ankle: float = -0.14
  swing_torso_pitch: float = 0.03
  ds_torso_pitch: float = 0.14
  cycle_period_s_old: float = 1.2
  phase_offset: float = 0.0
  swing_knee: float = 0.20
  swing_ankle_pitch: float = 0.06
  swing_hip_delta: float = 0.04

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
