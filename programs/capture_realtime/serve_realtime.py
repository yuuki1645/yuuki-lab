"""キャプチャデバイス → 低遅延 MJPEG + 録画（HLS 見返し / mp4 保存）。

常時:
  - multipart MJPEG（/stream.mjpg）で低遅延ライブ

録画開始後（POST /api/record/start）:
  - 同じフレームを ffmpeg に渡し HLS を生成（巻き戻し・シーク用）
  - 停止時（POST /api/record/stop）に video.mp4 を書き出す（映像のみ・音声なし）

前提:
  - pip install opencv-python
  - PATH 上に ffmpeg
  - キャプチャデバイスが他アプリに占有されていないこと

実行例:
  python programs/capture_realtime/serve_realtime.py
  python programs/capture_realtime/serve_realtime.py --width 1280 --height 720 --fps 30
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import cv2

# Windows (cp932) ではログの記号で UnicodeEncodeError になりやすい
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32" and hasattr(sys.stderr, "reconfigure"):
  sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
VIEWER_HTML = SCRIPT_DIR / "viewer.html"
RECORDINGS_DIR = SCRIPT_DIR / "recordings"

BOUNDARY = b"yuukiframe"
SESSION_ID_RE = re.compile(r"^[0-9A-Za-z_-]{6,64}$")

_frame_lock = threading.Lock()
_frame_cond = threading.Condition(_frame_lock)
_latest_jpeg: bytes | None = None
_frame_seq = 0
_frame_wh: tuple[int, int] | None = None
_out_fps: float = 30.0
_stop = threading.Event()

_rec_lock = threading.Lock()
_recorder = None  # RecordingSession | None（クラス定義後に代入）
_last_session_id: str | None = None
_last_mp4_name: str | None = None


def find_ffmpeg() -> str:
  path = shutil.which("ffmpeg")
  if not path:
    raise RuntimeError("ffmpeg が見つかりません。PATH を確認してください。")
  return path


def lan_ipv4_addresses() -> list[str]:
  found: set[str] = set()
  try:
    hostname = socket.gethostname()
    for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
      ip = info[4][0]
      if not ip.startswith("127."):
        found.add(ip)
  except OSError:
    pass
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    found.add(s.getsockname()[0])
    s.close()
  except OSError:
    pass
  return sorted(found)


def classify_ipv4(ip: str) -> str:
  parts = ip.split(".")
  if len(parts) != 4:
    return "other"
  try:
    a, b = int(parts[0]), int(parts[1])
  except ValueError:
    return "other"
  if a == 100 and 64 <= b <= 127:
    return "tailscale"
  if a == 172 and 16 <= b <= 31:
    return "virtual"
  if a == 192 and b == 168:
    return "lan"
  if a == 10:
    return "lan"
  return "other"


def ensure_firewall_rule(port: int) -> None:
  if sys.platform != "win32":
    print("Firewall helper is Windows-only; skip.")
    return
  rule_name = f"yuuki-lab capture_realtime {port}"
  subprocess.run(
    ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
    capture_output=True,
    text=True,
  )
  add = subprocess.run(
    [
      "netsh",
      "advfirewall",
      "firewall",
      "add",
      "rule",
      f"name={rule_name}",
      "dir=in",
      "action=allow",
      "protocol=TCP",
      f"localport={port}",
      "profile=any",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
  )
  if add.returncode == 0:
    print(f"Firewall: allowed inbound TCP {port} (rule: {rule_name})")
  else:
    print(
      "Firewall: failed to add rule. Run as Administrator:\n"
      f'  netsh advfirewall firewall add rule name="{rule_name}" '
      f"dir=in action=allow protocol=TCP localport={port} profile=any",
      file=sys.stderr,
    )


def list_devices(max_index: int = 10) -> None:
  print(f"Scanning capture devices (0..{max_index - 1}) via DirectShow...")
  found = 0
  for i in range(max_index):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
      w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
      h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
      fps = cap.get(cv2.CAP_PROP_FPS)
      print(f"  [{i}] OK  {w}x{h}  fps~={fps:.1f}")
      found += 1
      cap.release()
    else:
      print(f"  [{i}] —")
  print(f"Found {found} device(s)." if found else "No openable devices.")


def open_capture(
  device: int,
  width: int | None,
  height: int | None,
  fps: float | None,
) -> cv2.VideoCapture:
  cap = cv2.VideoCapture(device, cv2.CAP_DSHOW)
  if not cap.isOpened():
    raise RuntimeError(
      f"Failed to open device {device}. Try --list or stop capture_hls / other apps."
    )
  cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
  if width is not None:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
  if height is not None:
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
  if fps is not None:
    cap.set(cv2.CAP_PROP_FPS, fps)
  actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
  actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
  actual_fps = cap.get(cv2.CAP_PROP_FPS)
  print(f"Opened device {device}: {actual_w}x{actual_h} fps~={actual_fps:.1f}")
  return cap


class RecordingSession:
  """OpenCV フレーム → ffmpeg rawvideo → HLS。停止時に mp4 を生成する。"""

  def __init__(
    self,
    session_id: str,
    out_dir: Path,
    width: int,
    height: int,
    fps: float,
  ) -> None:
    self.session_id = session_id
    self.out_dir = out_dir
    self.width = width
    self.height = height
    self.fps = fps
    self.started_at = time.time()
    self._bytes_per_frame = width * height * 3
    self._ffmpeg = find_ffmpeg()
    self.out_dir.mkdir(parents=True, exist_ok=True)
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

  def write_frame(self, frame) -> None:  # noqa: ANN001 — numpy ndarray from OpenCV
    """BGR フレームを ffmpeg に渡す。失敗したらエラーを記録する。"""
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
    """HLS を終了し、可能なら video.mp4 を書き出してパスを返す。"""
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
      print(f"Recording HLS missing for {self.session_id}: {err}", file=sys.stderr)
      return None

    # 終了後は ENDLIST 付きでシークしやすいよう、copy で mp4 化
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
      print(
        f"mp4 mux failed ({self.session_id}): {mux.stderr}",
        file=sys.stderr,
      )
      return None
    return mp4_path


def publish_jpeg(jpeg: bytes) -> None:
  global _latest_jpeg, _frame_seq
  with _frame_cond:
    _latest_jpeg = jpeg
    _frame_seq += 1
    _frame_cond.notify_all()


def capture_loop(
  device: int,
  width: int | None,
  height: int | None,
  capture_fps: float | None,
  out_fps: float,
  quality: int,
) -> None:
  """キャプチャ → JPEG 公開。録画中は同じフレームを HLS エンコーダへも送る。"""
  global _frame_wh, _out_fps
  _out_fps = out_fps
  cap = open_capture(device, width, height, capture_fps)
  min_interval = 1.0 / max(out_fps, 1.0)
  next_send = 0.0
  encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]

  try:
    while not _stop.is_set():
      ok, frame = cap.read()
      if not ok or frame is None:
        time.sleep(0.01)
        continue

      now = time.perf_counter()
      if now < next_send:
        continue
      next_send = now + min_interval

      h, w = frame.shape[:2]
      _frame_wh = (w, h)

      with _rec_lock:
        rec = _recorder
      if rec is not None:
        rec.write_frame(frame)

      ok_enc, buf = cv2.imencode(".jpg", frame, encode_param)
      if not ok_enc:
        continue
      publish_jpeg(buf.tobytes())
  finally:
    cap.release()
    print("Capture loop stopped.")


def status_dict() -> dict:
  """Hub 向けステータス JSON。"""
  with _rec_lock:
    rec = _recorder
    last_id = _last_session_id
  recording = rec is not None
  session_id = rec.session_id if rec else last_id
  elapsed = (time.time() - rec.started_at) if rec else None
  hls_path = f"/recordings/{session_id}/index.m3u8" if session_id else None
  mp4_path = None
  if session_id and not recording:
    if (RECORDINGS_DIR / session_id / "video.mp4").is_file():
      mp4_path = f"/recordings/{session_id}/video.mp4"
  return {
    "ok": True,
    "recording": recording,
    "session_id": session_id,
    "elapsed_sec": round(elapsed, 1) if elapsed is not None else None,
    "hls_url": hls_path,
    "mp4_url": mp4_path,
    "frame_size": list(_frame_wh) if _frame_wh else None,
    "fps": _out_fps,
    "has_audio": False,
  }


def start_recording() -> tuple[int, dict]:
  """録画開始。既に録画中なら 409。"""
  global _recorder, _last_session_id, _last_mp4_name
  if _frame_wh is None:
    return 503, {"ok": False, "error": "no_frame", "message": "まだフレームがありません。"}
  with _rec_lock:
    if _recorder is not None:
      return 409, {"ok": False, "error": "already_recording", "message": "既に録画中です。"}
    w, h = _frame_wh
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RECORDINGS_DIR / session_id
    try:
      rec = RecordingSession(session_id, out_dir, w, h, _out_fps)
    except RuntimeError as e:
      return 500, {"ok": False, "error": "ffmpeg", "message": str(e)}
    _recorder = rec
    _last_session_id = session_id
    _last_mp4_name = None
  print(f"Recording started: {session_id} ({w}x{h} @ {_out_fps}fps)")
  return 200, status_dict()


def stop_recording() -> tuple[int, dict]:
  """録画停止して mp4 を生成する。"""
  global _recorder, _last_mp4_name
  with _rec_lock:
    rec = _recorder
    _recorder = None
  if rec is None:
    return 409, {"ok": False, "error": "not_recording", "message": "録画していません。"}
  print(f"Recording stopping: {rec.session_id} ...")
  mp4 = rec.stop()
  if mp4 is not None:
    _last_mp4_name = mp4.name
    print(f"Recording saved: {mp4}")
  else:
    print(f"Recording finished without mp4: {rec.session_id}", file=sys.stderr)
  body = status_dict()
  body["ok"] = True
  return 200, body


class RealtimeHandler(BaseHTTPRequestHandler):
  """MJPEG / API / 録画ファイル配信。"""

  def log_message(self, format: str, *args) -> None:
    # セグメント取得ログは抑制
    msg = format % args
    if "/recordings/" in msg and ".ts" in msg:
      return
    sys.stderr.write("%s - %s\n" % (self.address_string(), msg))

  def _cors(self) -> None:
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type")
    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    self.send_header("Pragma", "no-cache")

  def do_OPTIONS(self) -> None:
    self.send_response(204)
    self._cors()
    self.end_headers()

  def do_GET(self) -> None:
    path = unquote(self.path.split("?", 1)[0])
    if path in ("/", "/index.html"):
      self._serve_viewer()
      return
    if path in ("/stream.mjpg", "/stream.mjpeg"):
      self._serve_mjpeg()
      return
    if path == "/api/status":
      self._send_json(200, status_dict())
      return
    if path.startswith("/recordings/"):
      self._serve_recording_file(path)
      return
    self.send_error(404, "Not found")

  def do_POST(self) -> None:
    path = self.path.split("?", 1)[0]
    # ボディは今は使わないが読み捨てる
    length = int(self.headers.get("Content-Length", "0") or "0")
    if length > 0:
      self.rfile.read(length)
    if path == "/api/record/start":
      code, body = start_recording()
      self._send_json(code, body)
      return
    if path == "/api/record/stop":
      code, body = stop_recording()
      self._send_json(code, body)
      return
    self.send_error(404, "Not found")

  def _send_json(self, code: int, body: dict) -> None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    self.send_response(code)
    self._cors()
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(data)))
    self.end_headers()
    self.wfile.write(data)

  def _serve_viewer(self) -> None:
    body = VIEWER_HTML.read_bytes()
    self.send_response(200)
    self._cors()
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _serve_mjpeg(self) -> None:
    self.send_response(200)
    self._cors()
    self.send_header(
      "Content-Type",
      f"multipart/x-mixed-replace; boundary={BOUNDARY.decode('ascii')}",
    )
    self.end_headers()
    last_seq = -1
    try:
      while not _stop.is_set():
        with _frame_cond:
          if _frame_seq == last_seq:
            _frame_cond.wait(timeout=1.0)
          if _latest_jpeg is None:
            continue
          if _frame_seq == last_seq:
            continue
          last_seq = _frame_seq
          jpeg = _latest_jpeg
        header = (
          b"--"
          + BOUNDARY
          + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
          + str(len(jpeg)).encode("ascii")
          + b"\r\n\r\n"
        )
        self.wfile.write(header)
        self.wfile.write(jpeg)
        self.wfile.write(b"\r\n")
        self.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
      pass

  def _serve_recording_file(self, path: str) -> None:
    """`/recordings/<session>/<file>` を安全に返す。"""
    parts = path.strip("/").split("/")
    # recordings / session_id / filename
    if len(parts) != 3 or parts[0] != "recordings":
      self.send_error(404, "Not found")
      return
    session_id, name = parts[1], parts[2]
    if not SESSION_ID_RE.match(session_id):
      self.send_error(400, "Bad session id")
      return
    if "/" in name or "\\" in name or name in (".", ".."):
      self.send_error(400, "Bad file name")
      return
    # 許可拡張子のみ
    if not name.endswith((".m3u8", ".ts", ".mp4")):
      self.send_error(404, "Not found")
      return
    file_path = (RECORDINGS_DIR / session_id / name).resolve()
    try:
      file_path.relative_to(RECORDINGS_DIR.resolve())
    except ValueError:
      self.send_error(400, "Bad path")
      return
    if not file_path.is_file():
      self.send_error(404, "Not found")
      return
    data = file_path.read_bytes()
    if name.endswith(".m3u8"):
      ctype = "application/vnd.apple.mpegurl"
    elif name.endswith(".ts"):
      ctype = "video/mp2t"
    else:
      ctype = "video/mp4"
    self.send_response(200)
    self._cors()
    self.send_header("Content-Type", ctype)
    self.send_header("Content-Length", str(len(data)))
    if name.endswith(".m3u8"):
      self.send_header("Cache-Control", "no-cache")
    self.end_headers()
    self.wfile.write(data)


def print_access_urls(port: int) -> None:
  labels = {
    "lan": "LAN（推奨）",
    "tailscale": "Tailscale",
    "virtual": "仮想 NIC（通常は使わない）",
    "other": "その他",
  }
  print()
  print("=== iPad / 他端末（リアルタイム監視 + 録画 API） ===")
  print(f"  http://127.0.0.1:{port}/   (この PC のみ)")
  for ip in lan_ipv4_addresses():
    kind = classify_ipv4(ip)
    print(f"  http://{ip}:{port}/   [{labels.get(kind, kind)}]")
  print(f"  API: http://<IP>:{port}/api/status")
  print("停止: Ctrl+C")
  print("==========================================")
  print()


def run_session(args: argparse.Namespace) -> int:
  if not VIEWER_HTML.is_file():
    print(f"viewer.html not found: {VIEWER_HTML}", file=sys.stderr)
    return 1

  RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
  _stop.clear()
  cap_thread = threading.Thread(
    target=capture_loop,
    kwargs={
      "device": args.device,
      "width": args.width,
      "height": args.height,
      "capture_fps": args.capture_fps,
      "out_fps": args.fps,
      "quality": args.quality,
    },
    name="capture",
    daemon=True,
  )
  cap_thread.start()

  deadline = time.perf_counter() + 8.0
  while time.perf_counter() < deadline and not _stop.is_set():
    with _frame_lock:
      if _latest_jpeg is not None:
        break
    if not cap_thread.is_alive():
      print("Capture thread exited early.", file=sys.stderr)
      return 1
    time.sleep(0.05)
  else:
    if _latest_jpeg is None:
      print(
        "No frame yet (device busy or signal lost?). Continuing anyway…",
        file=sys.stderr,
      )

  server = ThreadingHTTPServer(("0.0.0.0", args.port), RealtimeHandler)
  http_thread = threading.Thread(
    target=server.serve_forever, name="http", daemon=True
  )
  http_thread.start()
  print_access_urls(args.port)

  def _request_stop(*_args: object) -> None:
    _stop.set()

  signal.signal(signal.SIGINT, _request_stop)
  if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _request_stop)

  try:
    while not _stop.is_set():
      if not cap_thread.is_alive():
        print("Capture thread stopped.")
        break
      time.sleep(0.2)
  finally:
    # 録画中なら止めてから終了
    with _rec_lock:
      rec = _recorder
    if rec is not None:
      stop_recording()
    _stop.set()
    with _frame_cond:
      _frame_cond.notify_all()
    server.shutdown()
    cap_thread.join(timeout=3)

  print("Stopped.")
  return 0


def main() -> int:
  parser = argparse.ArgumentParser(
    description="Low-latency MJPEG + record (HLS/mp4) for iPad lab use."
  )
  parser.add_argument("--list", action="store_true", help="List capture devices.")
  parser.add_argument("--device", type=int, default=0, help="Capture device index.")
  parser.add_argument("--width", type=int, default=1920, help="Request frame width.")
  parser.add_argument("--height", type=int, default=1080, help="Request frame height.")
  parser.add_argument("--capture-fps", type=float, default=60.0, help="Request capture FPS.")
  parser.add_argument("--fps", type=float, default=30.0, help="Output FPS (MJPEG + record).")
  parser.add_argument("--quality", type=int, default=70, help="JPEG quality 1-100.")
  parser.add_argument("--port", type=int, default=8766, help="HTTP port.")
  parser.add_argument(
    "--open-firewall",
    action="store_true",
    help="Add Windows firewall rule and exit.",
  )
  args = parser.parse_args()

  if args.open_firewall:
    ensure_firewall_rule(args.port)
    return 0
  if args.list:
    list_devices()
    return 0
  if not (1 <= args.quality <= 100):
    print("--quality must be 1..100", file=sys.stderr)
    return 1

  try:
    return run_session(args)
  except RuntimeError as e:
    print(e, file=sys.stderr)
    return 1
  except OSError as e:
    print(f"Server/OS error: {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
