"""キャプチャデバイス → 低遅延 MJPEG 配信（iPad リアルタイム監視用）。

HLS（programs/capture_hls）は巻き戻し向きで数秒遅れやすい。
こちらは「いまの映像をなるべく早く見る」ことに特化し、multipart MJPEG を HTTP で流す。

特徴:
  - 古いフレームは捨て、常に最新 JPEG だけを配信（キュー滞留による遅れを避ける）
  - iPad Chrome では <img src="/stream.mjpg"> で再生（追加コーデック不要）
  - 音声なし・シーク不可（監視専用）

前提:
  - pip install opencv-python
  - キャプチャデバイスが他アプリ / capture_hls に占有されていないこと
  - Windows ファイアウォールで --port（既定 8766）の受信を許可すること

実行例:
  python programs/capture_realtime/serve_realtime.py --list
  python programs/capture_realtime/serve_realtime.py
  python programs/capture_realtime/serve_realtime.py --device 0 --fps 30 --quality 70

  # 管理者 PowerShell で一度だけ
  python programs/capture_realtime/serve_realtime.py --open-firewall

iPad では起動ログの URL（例: http://192.168.x.x:8766/ ）を Chrome で開く。
"""

from __future__ import annotations

import argparse
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2

# Windows (cp932) ではログの記号で UnicodeEncodeError になりやすい
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32" and hasattr(sys.stderr, "reconfigure"):
  sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
VIEWER_HTML = SCRIPT_DIR / "viewer.html"

# multipart 境界文字列
BOUNDARY = b"yuukiframe"

# 共有: キャプチャスレッドが書く最新 JPEG
_frame_lock = threading.Lock()
_frame_cond = threading.Condition(_frame_lock)
_latest_jpeg: bytes | None = None
_frame_seq = 0
_stop = threading.Event()


def lan_ipv4_addresses() -> list[str]:
  """ループバック以外の IPv4 を列挙する（表示用）。"""
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
  """表示用に IP の種類をざっくり分類する。"""
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
  """Windows で当該 TCP ポートの受信許可ルールを追加する。"""
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
  """OpenCV / DirectShow で開けるデバイスを列挙する。"""
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
  """キャプチャを開き、可能ならバッファを最小化して遅延を抑える。"""
  cap = cv2.VideoCapture(device, cv2.CAP_DSHOW)
  if not cap.isOpened():
    raise RuntimeError(
      f"Failed to open device {device}. Try --list or stop capture_hls / other apps."
    )

  # ドライバが対応していればバッファを 1 にして古いフレームの滞留を減らす
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


def publish_jpeg(jpeg: bytes) -> None:
  """最新フレームを公開し、待っている配信スレッドを起こす。"""
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
  """キャプチャ → JPEG 化。配信 FPS を超える分は捨てて最新のみ残す。"""
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
        # 出力 FPS 制限: 読んだフレームは捨てて遅延を溜めない（最新優先）
        continue
      next_send = now + min_interval

      ok_enc, buf = cv2.imencode(".jpg", frame, encode_param)
      if not ok_enc:
        continue
      publish_jpeg(buf.tobytes())
  finally:
    cap.release()
    print("Capture loop stopped.")


class RealtimeHandler(BaseHTTPRequestHandler):
  """viewer HTML と MJPEG ストリームを返す。"""

  def log_message(self, format: str, *args) -> None:
    sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

  def _cors(self) -> None:
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    self.send_header("Pragma", "no-cache")

  def do_OPTIONS(self) -> None:
    self.send_response(204)
    self._cors()
    self.end_headers()

  def do_GET(self) -> None:
    path = self.path.split("?", 1)[0]
    if path in ("/", "/index.html"):
      self._serve_viewer()
      return
    if path in ("/stream.mjpg", "/stream.mjpeg"):
      self._serve_mjpeg()
      return
    self.send_error(404, "Not found")

  def _serve_viewer(self) -> None:
    body = VIEWER_HTML.read_bytes()
    self.send_response(200)
    self._cors()
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _serve_mjpeg(self) -> None:
    """multipart/x-mixed-replace で最新 JPEG を連続送信する。"""
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
          # 新しいフレームが来るまで待つ（最大 1 秒で生存確認）
          if _frame_seq == last_seq:
            _frame_cond.wait(timeout=1.0)
          if _latest_jpeg is None:
            continue
          if _frame_seq == last_seq:
            continue
          last_seq = _frame_seq
          jpeg = _latest_jpeg

        # パート書き込み中にさらに新しいフレームが来ても、次ループで追従する
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
      # クライアント切断は正常
      pass


def print_access_urls(port: int) -> None:
  """iPad 向け URL を表示する。"""
  labels = {
    "lan": "LAN（推奨）",
    "tailscale": "Tailscale",
    "virtual": "仮想 NIC（通常は使わない）",
    "other": "その他",
  }
  print()
  print("=== iPad / 他端末（リアルタイム監視） ===")
  print(f"  http://127.0.0.1:{port}/   (この PC のみ)")
  for ip in lan_ipv4_addresses():
    kind = classify_ipv4(ip)
    print(f"  http://{ip}:{port}/   [{labels.get(kind, kind)}]")
  print()
  print("注意: capture_hls と同時には同じキャプチャデバイスを開けません。")
  print("停止: Ctrl+C")
  print("==========================================")
  print()


def run_session(args: argparse.Namespace) -> int:
  """キャプチャスレッド + HTTP サーバを起動する。"""
  if not VIEWER_HTML.is_file():
    print(f"viewer.html not found: {VIEWER_HTML}", file=sys.stderr)
    return 1

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

  # 最初のフレーム待ち（デバイス占有失敗を早めに検知）
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
    _stop.set()
    with _frame_cond:
      _frame_cond.notify_all()
    server.shutdown()
    cap_thread.join(timeout=3)

  print("Stopped.")
  return 0


def main() -> int:
  parser = argparse.ArgumentParser(
    description="Low-latency MJPEG capture server for iPad live view."
  )
  parser.add_argument(
    "--list",
    action="store_true",
    help="List OpenCV/DirectShow capture devices and exit.",
  )
  parser.add_argument(
    "--device",
    type=int,
    default=0,
    help="Capture device index (default: 0). Use --list to find GC553Pro.",
  )
  parser.add_argument("--width", type=int, default=1920, help="Request frame width.")
  parser.add_argument("--height", type=int, default=1080, help="Request frame height.")
  parser.add_argument(
    "--capture-fps",
    type=float,
    default=60.0,
    help="Request capture FPS from device (default: 60).",
  )
  parser.add_argument(
    "--fps",
    type=float,
    default=30.0,
    help="Max JPEG stream FPS to clients (default: 30). Lower = less Wi-Fi load.",
  )
  parser.add_argument(
    "--quality",
    type=int,
    default=70,
    help="JPEG quality 1-100 (default: 70).",
  )
  parser.add_argument(
    "--port",
    type=int,
    default=8766,
    help="HTTP listen port (default: 8766).",
  )
  parser.add_argument(
    "--open-firewall",
    action="store_true",
    help="Add Windows inbound allow rule for --port and exit (Administrator).",
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
