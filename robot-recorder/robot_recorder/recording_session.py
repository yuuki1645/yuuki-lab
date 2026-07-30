"""OpenCV フレーム → ffmpeg HLS。停止時に video.mp4。"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2


def find_ffmpeg() -> str:
  path = shutil.which("ffmpeg")
  if not path:
    raise RuntimeError("ffmpeg が見つかりません。PATH を確認してください。")
  return path


def find_ffprobe() -> str | None:
  return shutil.which("ffprobe")


def ensure_m3u8_endlist(playlist: Path) -> None:
  """録画中は omit_endlist のため、mux 前に ENDLIST を付与する。"""
  text = playlist.read_text(encoding="utf-8", errors="replace")
  if "#EXT-X-ENDLIST" in text:
    return
  if not text.endswith("\n"):
    text += "\n"
  text += "#EXT-X-ENDLIST\n"
  playlist.write_text(text, encoding="utf-8")


def mp4_seems_valid(path: Path) -> bool:
  """moov 欠落などの壊れた mp4 を弾く。"""
  if not path.is_file() or path.stat().st_size < 1024:
    return False
  probe = find_ffprobe()
  if probe:
    r = subprocess.run(
      [
        probe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        str(path),
      ],
      capture_output=True,
      text=True,
      encoding="utf-8",
      errors="replace",
    )
    if r.returncode != 0:
      return False
    try:
      return float(r.stdout.strip().split(",")[0]) > 0
    except (ValueError, IndexError):
      return False
  # ffprobe が無い場合はファイル先頭〜末尾に moov/mdat があるか雑に確認
  raw = path.read_bytes()
  return b"moov" in raw and b"mdat" in raw


class RecordingSession:
  def __init__(
    self,
    take_id: str,
    out_dir: Path,
    width: int,
    height: int,
    fps: float,
  ) -> None:
    self.take_id = take_id
    self.out_dir = out_dir
    self.width = width
    self.height = height
    self.fps = max(float(fps), 1.0)
    self.started_at = time.time()
    self._t0_perf = time.perf_counter()
    self._frames_written = 0
    self._last_frame_bytes: bytes | None = None
    self._ffmpeg = find_ffmpeg()
    self.out_dir.mkdir(parents=True, exist_ok=True)
    (self.out_dir / "commands").mkdir(exist_ok=True)
    (self.out_dir / "sensors").mkdir(exist_ok=True)
    playlist = str(self.out_dir / "index.m3u8")
    segment = str(self.out_dir / "seg%05d.ts")
    cmd = [
      self._ffmpeg,
      "-hide_banner",
      "-loglevel",
      "error",
      "-f",
      "rawvideo",
      "-pix_fmt",
      "bgr24",
      "-s",
      f"{width}x{height}",
      "-r",
      str(self.fps),
      "-i",
      "pipe:0",
      "-an",
      "-c:v",
      "libx264",
      "-preset",
      "ultrafast",
      "-pix_fmt",
      "yuv420p",
      "-g",
      str(max(int(round(self.fps)), 15)),
      "-sc_threshold",
      "0",
      "-f",
      "hls",
      "-hls_time",
      "1",
      "-hls_list_size",
      "0",
      "-hls_flags",
      "independent_segments+omit_endlist",
      "-hls_segment_filename",
      segment,
      playlist,
    ]
    self._proc = subprocess.Popen(
      cmd,
      stdin=subprocess.PIPE,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.PIPE,
    )
    self._write_error: str | None = None

  def _write_raw(self, raw: bytes) -> None:
    if self._proc.stdin is None or self._proc.poll() is not None:
      return
    try:
      self._proc.stdin.write(raw)
    except BrokenPipeError:
      self._write_error = "ffmpeg pipe broken"
    except OSError as e:
      self._write_error = str(e)

  def write_frame(self, frame) -> None:  # noqa: ANN001
    """壁時計に合わせて不足フレームを直前フレームで埋め、再生時間が実時間に近くなるようにする。"""
    if self._proc.stdin is None or self._proc.poll() is not None:
      return
    if frame.shape[1] != self.width or frame.shape[0] != self.height:
      frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
    raw = frame.tobytes()
    self._last_frame_bytes = raw
    now = time.perf_counter()
    # 経過実時間から「何枚目まで書いてあるべきか」を決め、足りなければ複製して埋める
    target = int((now - self._t0_perf) * self.fps) + 1
    if target < 1:
      target = 1
    # 暴走防止（一時停止などで巨大ギャップが開いた場合は最大 2 秒分まで）
    max_catchup = self._frames_written + int(self.fps * 2) + 1
    if target > max_catchup:
      target = max_catchup
    while self._frames_written < target:
      self._write_raw(raw)
      self._frames_written += 1

  def stop(self) -> Path | None:
    # 停止直前まで壁時計分を埋める
    if self._last_frame_bytes is not None:
      now = time.perf_counter()
      target = int((now - self._t0_perf) * self.fps) + 1
      max_catchup = self._frames_written + int(self.fps * 2) + 1
      if target > max_catchup:
        target = max_catchup
      while self._frames_written < target:
        self._write_raw(self._last_frame_bytes)
        self._frames_written += 1

    if self._proc.stdin:
      try:
        self._proc.stdin.flush()
      except OSError:
        pass
      try:
        self._proc.stdin.close()
      except OSError:
        pass
    try:
      self._proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
      self._proc.kill()
      self._proc.wait(timeout=5)

    mp4_path = self.out_dir / "video.mp4"
    playlist = self.out_dir / "index.m3u8"
    if not playlist.is_file():
      err = ""
      if self._proc.stderr:
        err = self._proc.stderr.read().decode("utf-8", errors="replace")
      print(f"Recording HLS missing for {self.take_id}: {err}", file=sys.stderr)
      return None

    ensure_m3u8_endlist(playlist)

    # 壊れた途中 mp4 が残っていれば消す
    if mp4_path.is_file():
      try:
        mp4_path.unlink()
      except OSError:
        pass

    mux = subprocess.run(
      [
        self._ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(playlist),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(mp4_path),
      ],
      capture_output=True,
      text=True,
      encoding="utf-8",
      errors="replace",
    )
    if mux.returncode != 0 or not mp4_path.is_file() or not mp4_seems_valid(mp4_path):
      print(
        f"mp4 mux failed ({self.take_id}): {mux.stderr or 'invalid mp4'}",
        file=sys.stderr,
      )
      if mp4_path.is_file():
        try:
          mp4_path.unlink()
        except OSError:
          pass
      return None
    print(
      f"Recording muxed: {mp4_path.name} frames_written={self._frames_written}",
      file=sys.stderr,
    )
    return mp4_path
