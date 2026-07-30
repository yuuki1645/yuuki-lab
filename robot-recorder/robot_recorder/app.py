"""共有状態・キャプチャ・記録・ingest。"""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import cv2

from robot_recorder.config import AppConfig
from robot_recorder.disk import DiskStatus, disk_status
from robot_recorder.experiments import ExperimentStore
from robot_recorder.imu_bridge import ImuBridge
from robot_recorder.recording_session import RecordingSession
from robot_recorder.timestamp_overlay import burn_jst_timestamp

_JST = ZoneInfo("Asia/Tokyo")


class RecorderApp:
  def __init__(self, config: AppConfig) -> None:
    self.config = config
    self.store = ExperimentStore(config.data_root, config.default_format_id)
    self._stop = threading.Event()
    self._frame_lock = threading.Lock()
    self._frame_cond = threading.Condition(self._frame_lock)
    self._latest_jpeg: bytes | None = None
    self._frame_seq = 0
    self._frame_wh: tuple[int, int] | None = None
    self._rec_lock = threading.Lock()
    self._session: RecordingSession | None = None
    self._take_meta: dict[str, Any] | None = None
    self._last_take_id: str | None = None
    self._last_experiment_id: str | None = None
    self._disk_warning: str | None = None
    self._imu_lock = threading.Lock()
    self._latest_imu: dict[str, Any] | None = None
    self._ingest_lock = threading.Lock()
    self.imu_bridge: ImuBridge | None = None

  def start_background(self) -> None:
    self.config.data_root.mkdir(parents=True, exist_ok=True)
    (self.config.data_root / "experiments").mkdir(exist_ok=True)
    threading.Thread(target=self._capture_loop, name="capture", daemon=True).start()
    threading.Thread(target=self._disk_watch_loop, name="disk", daemon=True).start()
    if self.config.imu_bridge_enabled:
      self.imu_bridge = ImuBridge(
        self,
        self.config.robot_daemon_url,
        rate_hz=self.config.imu_bridge_rate_hz,
      )
      self.imu_bridge.start()

  def stop(self) -> None:
    self._stop.set()
    if self.imu_bridge is not None:
      self.imu_bridge.stop()
    with self._rec_lock:
      sess = self._session
      self._session = None
    if sess is not None:
      sess.stop()

  def _disk_watch_loop(self) -> None:
    interval = max(5.0, self.config.recording.disk_check_interval_sec)
    while not self._stop.wait(interval):
      st = disk_status(self.config.data_root, self.config.recording.min_free_bytes)
      with self._rec_lock:
        recording = self._session is not None
      if recording and not st.ok_for_record:
        self._disk_warning = st.warning
      elif st.ok_for_record:
        self._disk_warning = None

  def check_disk(self) -> DiskStatus:
    return disk_status(self.config.data_root, self.config.recording.min_free_bytes)

  def publish_jpeg(self, jpeg: bytes) -> None:
    with self._frame_cond:
      self._latest_jpeg = jpeg
      self._frame_seq += 1
      self._frame_cond.notify_all()

  def wait_jpeg(self, last_seq: int, timeout: float) -> tuple[int, bytes | None]:
    with self._frame_cond:
      if self._frame_seq == last_seq:
        self._frame_cond.wait(timeout=timeout)
      return self._frame_seq, self._latest_jpeg

  def _capture_loop(self) -> None:
    cap_cfg = self.config.capture
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), int(cap_cfg.jpeg_quality)]
    min_interval = 1.0 / max(cap_cfg.fps, 1.0)

    while not self._stop.is_set():
      backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
      cap = cv2.VideoCapture(cap_cfg.device, backend)
      if not cap.isOpened():
        print(
          f"カメラを開けませんでした: device={cap_cfg.device}（再試行します）",
          file=__import__("sys").stderr,
        )
        time.sleep(2.0)
        continue
      cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
      cap.set(cv2.CAP_PROP_FRAME_WIDTH, cap_cfg.width)
      cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_cfg.height)
      cap.set(cv2.CAP_PROP_FPS, cap_cfg.fps)
      next_send = 0.0
      print(
        f"Capture opened: device={cap_cfg.device} "
        f"req={cap_cfg.width}x{cap_cfg.height}@{cap_cfg.fps}"
      )
      try:
        while not self._stop.is_set():
          ok, frame = cap.read()
          if not ok or frame is None:
            time.sleep(0.01)
            continue
          now = time.perf_counter()
          if now < next_send:
            continue
          next_send = now + min_interval
          if cap_cfg.burn_timestamp:
            burn_jst_timestamp(frame)
          h, w = frame.shape[:2]
          self._frame_wh = (w, h)
          with self._rec_lock:
            sess = self._session
          if sess is not None:
            sess.write_frame(frame)
          ok_enc, buf = cv2.imencode(".jpg", frame, encode_param)
          if ok_enc:
            self.publish_jpeg(buf.tobytes())
      finally:
        cap.release()
        print("Capture device released; will retry if still running.")
    print("Capture loop stopped.")

  def status_dict(self) -> dict[str, Any]:
    with self._rec_lock:
      sess = self._session
      last_take = self._last_take_id
      last_exp = self._last_experiment_id
      disk_warn = self._disk_warning
    recording = sess is not None
    take_id = sess.take_id if sess else last_take
    exp_id = self.store.get_active_experiment_id() if recording else (
      last_exp or self.store.get_active_experiment_id()
    )
    if recording and self._take_meta:
      exp_id = self._take_meta.get("experiment_id", exp_id)
    elapsed = (time.time() - sess.started_at) if sess else None
    disk = self.check_disk()
    hls_url = None
    mp4_url = None
    if take_id and exp_id:
      base = f"/data/experiments/{exp_id}/takes/{take_id}"
      hls_url = f"{base}/index.m3u8"
      take_dir = self.store.takes_dir(exp_id) / take_id
      if not recording and (take_dir / "video.mp4").is_file():
        mp4_url = f"{base}/video.mp4"
    return {
      "ok": True,
      "recording": recording,
      "experiment_id": self.store.get_active_experiment_id(),
      "take_id": take_id,
      "elapsed_sec": round(elapsed, 1) if elapsed is not None else None,
      "hls_url": hls_url,
      "mp4_url": mp4_url,
      "frame_size": list(self._frame_wh) if self._frame_wh else None,
      "fps": self.config.capture.fps,
      "burn_timestamp": self.config.capture.burn_timestamp,
      "format_id": self.config.default_format_id,
      "data_root": str(self.config.data_root),
      "disk": {
        "free_bytes": disk.free_bytes,
        "total_bytes": disk.total_bytes,
        "ok_for_record": disk.ok_for_record,
        "warning": disk_warn or disk.warning,
      },
      "imu_bridge": self.imu_bridge.snapshot() if self.imu_bridge else {"status": "disabled"},
    }

  def start_recording(self) -> tuple[int, dict[str, Any]]:
    if self._frame_wh is None:
      return 503, {
        "ok": False,
        "error": "no_frame",
        "message": "まだフレームがありません。",
      }
    disk = self.check_disk()
    if not disk.ok_for_record:
      return 507, {
        "ok": False,
        "error": "disk_full",
        "message": disk.warning or "ディスク空き不足",
        "disk": {
          "free_bytes": disk.free_bytes,
          "ok_for_record": False,
          "warning": disk.warning,
        },
      }
    exp_id = self.store.get_active_experiment_id()
    if not exp_id:
      return 400, {
        "ok": False,
        "error": "no_experiment",
        "message": "録り込む実験フォルダを選択してください。",
      }
    exp = self.store.get(exp_id)
    if exp is None:
      return 400, {"ok": False, "error": "experiment_missing", "message": "実験がありません。"}

    with self._rec_lock:
      if self._session is not None:
        return 409, {
          "ok": False,
          "error": "already_recording",
          "message": "既に録画中です。",
        }
      w, h = self._frame_wh
      take_id = datetime.now(_JST).strftime("%Y%m%d_%H%M%S")
      out_dir = self.store.takes_dir(exp_id) / take_id
      try:
        sess = RecordingSession(take_id, out_dir, w, h, self.config.capture.fps)
      except RuntimeError as e:
        return 500, {"ok": False, "error": "ffmpeg", "message": str(e)}
      t0 = time.time()
      meta = {
        "take_id": take_id,
        "experiment_id": exp_id,
        "format_id": exp.format_id,
        "video_t0_unix": t0,
        "video_t0_jst": datetime.now(_JST).isoformat(timespec="milliseconds"),
        "width": w,
        "height": h,
        "fps": self.config.capture.fps,
        "burn_timestamp": self.config.capture.burn_timestamp,
      }
      out_dir.mkdir(parents=True, exist_ok=True)
      (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
      )
      self._session = sess
      self._take_meta = meta
      self._last_take_id = take_id
      self._last_experiment_id = exp_id
      self._disk_warning = None
    print(f"Recording started: {exp_id}/{take_id}")
    return 200, self.status_dict()

  def stop_recording(self) -> tuple[int, dict[str, Any]]:
    with self._rec_lock:
      sess = self._session
      meta = self._take_meta
      self._session = None
      self._take_meta = None
    if sess is None:
      return 409, {
        "ok": False,
        "error": "not_recording",
        "message": "録画していません。",
      }
    print(f"Recording stopping: {sess.take_id} ...")
    mp4 = sess.stop()
    if meta and mp4 is not None:
      meta["video_file"] = "video.mp4"
      meta["stopped_at_unix"] = time.time()
      meta_path = sess.out_dir / "meta.json"
      meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
      )
      print(f"Recording saved: {mp4}")
    return 200, self.status_dict()

  def ingest_command(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """recording 中のみ take の commands/servo.jsonl に追記。常に 200（制御側を止めない）。"""
    line = dict(payload)
    line.setdefault("recorder_recv_unix", time.time())
    with self._rec_lock:
      sess = self._session
      out_dir = sess.out_dir if sess else None
    if out_dir is None:
      return 200, {"ok": True, "recorded": False, "reason": "not_recording"}
    path = out_dir / "commands" / "servo.jsonl"
    with self._ingest_lock:
      with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return 200, {"ok": True, "recorded": True}

  def ingest_imu(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    sample = dict(payload)
    sample.setdefault("recorder_recv_unix", time.time())
    with self._imu_lock:
      self._latest_imu = sample
    with self._rec_lock:
      sess = self._session
      out_dir = sess.out_dir if sess else None
    if out_dir is None:
      return 200, {"ok": True, "recorded": False, "reason": "not_recording"}
    path = out_dir / "sensors" / "imu.jsonl"
    with self._ingest_lock:
      with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    return 200, {"ok": True, "recorded": True}

  def latest_imu(self) -> dict[str, Any] | None:
    with self._imu_lock:
      return dict(self._latest_imu) if self._latest_imu else None

  def resolve_data_file(self, rel: str) -> Path | None:
    """/data/ 以下の安全な相対パスを絶対 Path に。"""
    rel = rel.replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
      return None
    full = (self.config.data_root / rel).resolve()
    root = self.config.data_root.resolve()
    try:
      full.relative_to(root)
    except ValueError:
      return None
    if not full.is_file():
      return None
    return full
