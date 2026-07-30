"""設定読み込み（config.local.yaml > config.example.yaml）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CaptureConfig:
  device: int = 0
  width: int = 1280
  height: int = 720
  fps: float = 30.0
  jpeg_quality: int = 80
  burn_timestamp: bool = True


@dataclass
class RecordingConfig:
  min_free_bytes: int = 10 * 1024 * 1024 * 1024
  disk_check_interval_sec: float = 30.0


@dataclass
class AppConfig:
  data_root: Path = field(default_factory=lambda: Path.home() / "yuuki-lab-data")
  host: str = "0.0.0.0"
  port: int = 8766
  capture: CaptureConfig = field(default_factory=CaptureConfig)
  recording: RecordingConfig = field(default_factory=RecordingConfig)
  default_format_id: str = "robot_take_v0"
  robot_daemon_url: str = "http://192.168.100.50:5000"


def _as_dict(path: Path) -> dict[str, Any]:
  if not path.is_file():
    return {}
  with path.open(encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
  if not isinstance(data, dict):
    raise ValueError(f"設定はマッピングである必要があります: {path}")
  return data


def load_config(config_path: Path | None = None) -> AppConfig:
  """local があれば優先し、example で欠けを埋める。"""
  example = PACKAGE_ROOT / "config.example.yaml"
  local = PACKAGE_ROOT / "config.local.yaml"
  merged: dict[str, Any] = {}
  merged.update(_as_dict(example))
  if config_path is not None:
    merged.update(_as_dict(config_path))
  elif local.is_file():
    merged.update(_as_dict(local))

  cap_raw = merged.get("capture") or {}
  rec_raw = merged.get("recording") or {}
  daemon_raw = merged.get("robot_daemon") or {}

  data_root = Path(str(merged.get("data_root") or (Path.home() / "yuuki-lab-data")))
  return AppConfig(
    data_root=data_root.expanduser().resolve(),
    host=str(merged.get("host") or "0.0.0.0"),
    port=int(merged.get("port") or 8766),
    capture=CaptureConfig(
      device=int(cap_raw.get("device", 0)),
      width=int(cap_raw.get("width", 1280)),
      height=int(cap_raw.get("height", 720)),
      fps=float(cap_raw.get("fps", 30)),
      jpeg_quality=int(cap_raw.get("jpeg_quality", 80)),
      burn_timestamp=bool(cap_raw.get("burn_timestamp", True)),
    ),
    recording=RecordingConfig(
      min_free_bytes=int(rec_raw.get("min_free_bytes", 10 * 1024 * 1024 * 1024)),
      disk_check_interval_sec=float(rec_raw.get("disk_check_interval_sec", 30)),
    ),
    default_format_id=str(merged.get("default_format_id") or "robot_take_v0"),
    robot_daemon_url=str(daemon_raw.get("url") or "http://192.168.100.50:5000"),
  )
