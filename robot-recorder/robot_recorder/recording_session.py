"""OpenCV フレーム → ffmpeg HLS。停止時に video.mp4。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import cv2


def find_ffmpeg() -> str:
  path = shutil.which("ffmpeg")
  if not path:
    raise RuntimeError("ffmpeg が見つかりません。PATH を確認してください。")
  return path


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
    self.fps = fps
    self.started_at = __import__("time").time()
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
      str(fps),
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
      str(max(int(round(fps)), 15)),
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

  def write_frame(self, frame) -> None:  # noqa: ANN001
    if self._proc.stdin is None or self._proc.poll() is not None:
      return
    if frame.shape[1] != self.width or frame.shape[0] != self.height:
      frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
    try:
      self._proc.stdin.write(frame.tobytes())
    except BrokenPipeError:
      self._write_error = "ffmpeg pipe broken"
    except OSError as e:
      self._write_error = str(e)

  def stop(self) -> Path | None:
    if self._proc.stdin:
      try:
        self._proc.stdin.close()
      except OSError:
        pass
    try:
      self._proc.wait(timeout=15)
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
        str(mp4_path),
      ],
      capture_output=True,
      text=True,
      encoding="utf-8",
      errors="replace",
    )
    if mux.returncode != 0 or not mp4_path.is_file():
      print(f"mp4 mux failed ({self.take_id}): {mux.stderr}", file=sys.stderr)
      return None
    return mp4_path
