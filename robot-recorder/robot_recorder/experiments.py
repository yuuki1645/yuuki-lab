"""実験フォルダ（DATA_ROOT/experiments）の管理。"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"^[0-9A-Za-z][0-9A-Za-z_-]{0,63}$")
_SLUG = re.compile(r"[^0-9A-Za-z_-]+")


@dataclass
class Experiment:
  id: str
  name: str
  format_id: str
  created_at: float
  updated_at: float

  def to_dict(self) -> dict[str, Any]:
    return {
      "id": self.id,
      "name": self.name,
      "format_id": self.format_id,
      "created_at": self.created_at,
      "updated_at": self.updated_at,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Experiment:
    return cls(
      id=str(data["id"]),
      name=str(data.get("name") or data["id"]),
      format_id=str(data.get("format_id") or "robot_take_v0"),
      created_at=float(data.get("created_at") or time.time()),
      updated_at=float(data.get("updated_at") or time.time()),
    )


class ExperimentStore:
  def __init__(self, data_root: Path, default_format_id: str) -> None:
    self.data_root = data_root
    self.default_format_id = default_format_id
    self.experiments_dir = data_root / "experiments"
    self.state_path = data_root / "recorder_state.json"
    self.experiments_dir.mkdir(parents=True, exist_ok=True)

  def _exp_dir(self, exp_id: str) -> Path:
    return self.experiments_dir / exp_id

  def _meta_path(self, exp_id: str) -> Path:
    return self._exp_dir(exp_id) / "experiment.json"

  def _load_state(self) -> dict[str, Any]:
    if not self.state_path.is_file():
      return {}
    try:
      return json.loads(self.state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
      return {}

  def _save_state(self, state: dict[str, Any]) -> None:
    self.data_root.mkdir(parents=True, exist_ok=True)
    self.state_path.write_text(
      json.dumps(state, ensure_ascii=False, indent=2) + "\n",
      encoding="utf-8",
    )

  def get_active_experiment_id(self) -> str | None:
    sid = self._load_state().get("active_experiment_id")
    return str(sid) if sid else None

  def set_active_experiment_id(self, exp_id: str | None) -> None:
    state = self._load_state()
    if exp_id is None:
      state.pop("active_experiment_id", None)
    else:
      if self.get(exp_id) is None:
        raise KeyError(exp_id)
      state["active_experiment_id"] = exp_id
    self._save_state(state)

  def list_experiments(self) -> list[Experiment]:
    items: list[Experiment] = []
    if not self.experiments_dir.is_dir():
      return items
    for child in sorted(self.experiments_dir.iterdir()):
      meta = child / "experiment.json"
      if not meta.is_file():
        continue
      try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        items.append(Experiment.from_dict(data))
      except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        continue
    return items

  def get(self, exp_id: str) -> Experiment | None:
    path = self._meta_path(exp_id)
    if not path.is_file():
      return None
    try:
      return Experiment.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
      return None

  def _unique_id(self, name: str) -> str:
    base = _SLUG.sub("-", name.strip()).strip("-_") or "experiment"
    base = base[:48]
    candidate = base
    n = 2
    while self._meta_path(candidate).is_file():
      candidate = f"{base}_{n}"
      n += 1
    if not _SAFE_ID.match(candidate):
      candidate = f"exp_{int(time.time())}"
    return candidate

  def create(self, name: str, format_id: str | None = None) -> Experiment:
    name = (name or "").strip()
    if not name:
      raise ValueError("name は必須です")
    exp_id = self._unique_id(name)
    now = time.time()
    exp = Experiment(
      id=exp_id,
      name=name,
      format_id=format_id or self.default_format_id,
      created_at=now,
      updated_at=now,
    )
    d = self._exp_dir(exp_id)
    d.mkdir(parents=True, exist_ok=False)
    (d / "takes").mkdir(parents=True, exist_ok=True)
    self._meta_path(exp_id).write_text(
      json.dumps(exp.to_dict(), ensure_ascii=False, indent=2) + "\n",
      encoding="utf-8",
    )
    if self.get_active_experiment_id() is None:
      self.set_active_experiment_id(exp_id)
    return exp

  def rename(self, exp_id: str, name: str) -> Experiment:
    exp = self.get(exp_id)
    if exp is None:
      raise KeyError(exp_id)
    name = (name or "").strip()
    if not name:
      raise ValueError("name は必須です")
    exp.name = name
    exp.updated_at = time.time()
    self._meta_path(exp_id).write_text(
      json.dumps(exp.to_dict(), ensure_ascii=False, indent=2) + "\n",
      encoding="utf-8",
    )
    return exp

  def delete(self, exp_id: str) -> None:
    if self.get(exp_id) is None:
      raise KeyError(exp_id)
    # 中に take があると誤削除防止
    takes = self._exp_dir(exp_id) / "takes"
    if takes.is_dir() and any(takes.iterdir()):
      raise OSError("takes が空でないため削除できません（中身を移すか空にしてから）")
    shutil.rmtree(self._exp_dir(exp_id))
    if self.get_active_experiment_id() == exp_id:
      self.set_active_experiment_id(None)

  def takes_dir(self, exp_id: str) -> Path:
    return self._exp_dir(exp_id) / "takes"

  def list_takes(self, exp_id: str) -> list[str]:
    d = self.takes_dir(exp_id)
    if not d.is_dir():
      return []
    return sorted(
      p.name for p in d.iterdir() if p.is_dir() and (p / "meta.json").is_file()
    )

  def get_take_meta(self, exp_id: str, take_id: str) -> dict[str, Any] | None:
    """take の meta.json を読む。無ければ None。"""
    path = self.takes_dir(exp_id) / take_id / "meta.json"
    if not path.is_file():
      return None
    try:
      data = json.loads(path.read_text(encoding="utf-8"))
      return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError):
      return None

  def describe_take(self, exp_id: str, take_id: str) -> dict[str, Any] | None:
    """ビュワー用: meta + ファイル有無 + URL。"""
    take_dir = self.takes_dir(exp_id) / take_id
    meta = self.get_take_meta(exp_id, take_id)
    if meta is None or not take_dir.is_dir():
      return None
    video_name = str(meta.get("video_file") or "video.mp4")
    video_path = take_dir / video_name
    has_video = video_path.is_file() and video_path.stat().st_size > 1024
    has_hls = (take_dir / "index.m3u8").is_file()
    has_imu = (take_dir / "sensors" / "imu.jsonl").is_file()
    has_commands = (take_dir / "commands" / "servo.jsonl").is_file()
    base = f"/data/experiments/{exp_id}/takes/{take_id}"
    return {
      "take_id": take_id,
      "experiment_id": exp_id,
      "format_id": str(meta.get("format_id") or "robot_take_v0"),
      "meta": meta,
      "has_video": has_video,
      "has_hls": has_hls,
      "has_imu": has_imu,
      "has_commands": has_commands,
      "video_url": f"{base}/{video_name}" if has_video else None,
      "hls_url": f"{base}/index.m3u8" if has_hls else None,
      "imu_url": f"{base}/sensors/imu.jsonl" if has_imu else None,
      "commands_url": f"{base}/commands/servo.jsonl" if has_commands else None,
      "meta_url": f"{base}/meta.json",
    }

  def list_take_descriptions(self, exp_id: str) -> list[dict[str, Any]]:
    if self.get(exp_id) is None:
      raise KeyError(exp_id)
    out: list[dict[str, Any]] = []
    for tid in self.list_takes(exp_id):
      desc = self.describe_take(exp_id, tid)
      if desc is not None:
        out.append(desc)
    return out
