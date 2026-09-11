"""OpenCV フレーム → ffmpeg HLS。停止時に video.mp4。"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2


def find_ffmpeg() -> str | None:
  """PATH 上の ffmpeg。無い環境では OpenCV 書き出しに落とす。"""
  return shutil.which("ffmpeg")


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
    self._last_bgr = None
    self._write_error: str | None = None
    self._ffmpeg = find_ffmpeg()
    self._proc: subprocess.Popen[bytes] | None = None
    self._writer: cv2.VideoWriter | None = None
    self.out_dir.mkdir(parents=True, exist_ok=True)
    (self.out_dir / "commands").mkdir(exist_ok=True)
    (self.out_dir / "sensors").mkdir(exist_ok=True)
    if self._ffmpeg:
      self._start_ffmpeg(width, height)
    else:
      # 新 PC など ffmpeg 未導入でも本記録できるようにする
      self._start_opencv_writer(width, height)
      print("ffmpeg が無いため OpenCV で video.mp4 を書きます", file=sys.stderr)

  def _start_ffmpeg(self, width: int, height: int) -> None:
    assert self._ffmpeg is not None
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

  def _start_opencv_writer(self, width: int, height: int) -> None:
    """ffmpeg 無しでも take に mp4 を残す。"""
    path = str(self.out_dir / "video.mp4")
    last_err = "VideoWriter を開けませんでした"
    for fourcc_name in ("mp4v", "avc1", "XVID"):
      writer = cv2.VideoWriter(
        path,
        cv2.VideoWriter_fourcc(*fourcc_name),
        self.fps,
        (width, height),
      )
      if writer.isOpened():
        self._writer = writer
        return
      writer.release()
      last_err = f"fourcc={fourcc_name} で開けません"
    raise RuntimeError(f"映像ファイルを作成できません（{last_err}）。ffmpeg の導入を推奨します。")

  def _alive(self) -> bool:
    if self._writer is not None:
      return self._writer.isOpened()
    return self._proc is not None and self._proc.stdin is not None and self._proc.poll() is None

  def _emit(self, frame, raw: bytes) -> None:  # noqa: ANN001
    if self._writer is not None:
      self._writer.write(frame)
      return
    if self._proc is None or self._proc.stdin is None or self._proc.poll() is not None:
      return
    try:
      self._proc.stdin.write(raw)
    except BrokenPipeError:
      self._write_error = "ffmpeg pipe broken"
    except OSError as e:
      self._write_error = str(e)

  def _catchup_target(self) -> int:
    now = time.perf_counter()
    target = int((now - self._t0_perf) * self.fps) + 1
    if target < 1:
      target = 1
    max_catchup = self._frames_written + int(self.fps * 2) + 1
    return min(target, max_catchup)

  def write_frame(self, frame) -> None:  # noqa: ANN001
    """壁時計に合わせて不足フレームを直前フレームで埋め、再生時間が実時間に近くなるようにする。"""
    if not self._alive():
      return
    if frame.shape[1] != self.width or frame.shape[0] != self.height:
      frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
    raw = frame.tobytes()
    self._last_frame_bytes = raw
    self._last_bgr = frame
    while self._frames_written < self._catchup_target():
      self._emit(frame, raw)
      self._frames_written += 1

  def stop(self) -> Path | None:
    if self._last_bgr is not None and self._last_frame_bytes is not None and self._alive():
      while self._frames_written < self._catchup_target():
        self._emit(self._last_bgr, self._last_frame_bytes)
        self._frames_written += 1

    if self._writer is not None:
      self._writer.release()
      self._writer = None
      mp4_path = self.out_dir / "video.mp4"
      if mp4_path.is_file() and mp4_path.stat().st_size > 1024:
        print(
          f"Recording saved (OpenCV): {mp4_path.name} frames_written={self._frames_written}",
          file=sys.stderr,
        )
        return mp4_path
      print(f"Recording OpenCV mp4 missing for {self.take_id}", file=sys.stderr)
      return None

    if self._proc is None:
      return None
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

    if mp4_path.is_file():
      try:
        mp4_path.unlink()
      except OSError:
        pass

    mux = subprocess.run(
      [
        self._ffmpeg or "ffmpeg",
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
