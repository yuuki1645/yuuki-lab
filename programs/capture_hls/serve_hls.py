"""キャプチャデバイス → HLS 出力 + LAN 向け HTTP 配信（Windows / iPad 確認用）。

AVerMedia Live Gamer ULTRA S 等の DirectShow デバイスを ffmpeg で HLS に切り出し、
同じ PC 上の HTTP サーバで LAN 内の iPad（Chrome 等）から視聴・シークできるようにする。

前提:
  - PATH 上に ffmpeg があること（確認済みの環境想定）
  - キャプチャデバイスが他アプリに占有されていないこと
  - Windows ファイアウォールで --port（既定 8765）の受信を許可すること

依存:
  標準ライブラリのみ（追加 pip 不要）

実行例:
  # デバイス一覧（ffmpeg -list_devices）
  python programs/capture_hls/serve_hls.py --list

  # 録画 + 配信開始（Ctrl+C で停止）
  python programs/capture_hls/serve_hls.py

  # NVIDIA GPU（NVENC）+ 既定の短い HLS 断片（1 秒）
  python programs/capture_hls/serve_hls.py --nvenc

  # ポート・出力先・長さを指定（例: 60 秒で自動終了）
  python programs/capture_hls/serve_hls.py --port 8765 --duration 60

iPad では起動ログに出る URL（例: http://192.168.x.x:8765/ ）を Chrome で開く。
"""

from __future__ import annotations

import argparse
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# このスクリプトと同じディレクトリ
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = SCRIPT_DIR / "out"
VIEWER_HTML = SCRIPT_DIR / "viewer.html"

# 実機で確認済みの既定デバイス名（ffmpeg -list_devices の表示名）
DEFAULT_VIDEO = "Live Gamer ULTRA S GC553Pro"
DEFAULT_AUDIO = "HDMI (Live Gamer ULTRA S GC553Pro)"


def find_ffmpeg() -> str:
  """PATH 上の ffmpeg 実行ファイルを返す。無ければ終了用に例外。"""
  path = shutil.which("ffmpeg")
  if not path:
    raise RuntimeError(
      "ffmpeg が見つかりません。PATH を確認するか、https://www.gyan.dev/ffmpeg/ 等から入れてください。"
    )
  return path


def list_dshow_devices(ffmpeg: str) -> int:
  """DirectShow デバイス一覧を表示する（終了コードは ffmpeg に合わせる）。"""
  # -list_devices は入力オープンに失敗して非ゼロになりがちなので、出力だけ見せる
  proc = subprocess.run(
    [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
  )
  # デバイス名は stderr に出る
  text = (proc.stderr or "") + (proc.stdout or "")
  print(text)
  return 0


def lan_ipv4_addresses() -> list[str]:
  """ループバック以外の IPv4 をできるだけ列挙する（表示用）。"""
  found: set[str] = set()
  try:
    hostname = socket.gethostname()
    for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
      ip = info[4][0]
      if not ip.startswith("127."):
        found.add(ip)
  except OSError:
    pass

  # UDP で「出ていく NIC」を推定（実際にはパケットは送らない）
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
  # Tailscale の CGNAT 帯
  if a == 100 and 64 <= b <= 127:
    return "tailscale"
  # よくある仮想 NIC（Hyper-V / Docker / WSL 系）
  if a == 172 and 16 <= b <= 31:
    return "virtual"
  if a == 192 and b == 168:
    return "lan"
  if a == 10:
    return "lan"
  return "other"


def ensure_firewall_rule(port: int) -> None:
  """Windows で当該 TCP ポートの受信許可ルールを追加する（管理者権限が必要な場合あり）。"""
  if sys.platform != "win32":
    print("Firewall helper is Windows-only; skip.")
    return
  rule_name = f"yuuki-lab capture_hls {port}"
  # 既存ルールを消してから入れ直す（ポート変更時のため）
  subprocess.run(
    [
      "netsh",
      "advfirewall",
      "firewall",
      "delete",
      "rule",
      f"name={rule_name}",
    ],
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
      "Firewall: failed to add rule (管理者として PowerShell を開き、"
      f"  netsh advfirewall firewall add rule name=\"{rule_name}\" "
      f"dir=in action=allow protocol=TCP localport={port} profile=any\n"
      "  を実行してください)。",
      file=sys.stderr,
    )
    if add.stdout:
      print(add.stdout, file=sys.stderr)
    if add.stderr:
      print(add.stderr, file=sys.stderr)


class CorsHlsHandler(SimpleHTTPRequestHandler):
  """HLS / HTML 用。CORS と正しい MIME を付与する。"""

  # ディレクトリトラバーサル防止のため directory はサーバ生成時に partial で固定する

  extensions_map = {
    **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
    ".m4s": "video/iso.segment",
    ".html": "text/html; charset=utf-8",
  }

  def end_headers(self) -> None:
    # iPad から別オリジンで触る場合にも備えて緩く許可（LAN 実験用）
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "*")
    # ライブプレイリストはキャッシュさせない
    if self.path.endswith(".m3u8"):
      self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
    super().end_headers()

  def do_OPTIONS(self) -> None:
    self.send_response(204)
    self.end_headers()

  def log_message(self, format: str, *args) -> None:
    # セグメント取得でログが埋まるので簡潔に
    sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


def prepare_out_dir(out_dir: Path) -> None:
  """出力ディレクトリを用意し、viewer.html を配置する。"""
  out_dir.mkdir(parents=True, exist_ok=True)
  # 前回の断片が残っているとプレイリストと不整合になりやすいので掃除
  for pattern in ("*.ts", "*.m3u8", "*.m4s", "*.tmp"):
    for p in out_dir.glob(pattern):
      try:
        p.unlink()
      except OSError:
        pass
  dest = out_dir / "index.html"
  dest.write_text(VIEWER_HTML.read_text(encoding="utf-8"), encoding="utf-8")


def build_video_encode_args(*, nvenc: bool, framerate: int, hls_time: float) -> list[str]:
  """映像エンコード引数。NVENC 時は低遅延寄り、それ以外は libx264 ultrafast。"""
  # セグメント境界で切れやすいよう、GOP を hls_time 秒相当に近づける
  gop = max(int(round(framerate * max(hls_time, 0.5))), 15)

  if nvenc:
    # RTX 4080 SUPER 等: NVENC ハードウェアエンコード（CPU 解放・エンコード遅延低減）
    return [
      "-c:v",
      "h264_nvenc",
      "-preset",
      "p1",  # 最速寄り
      "-tune",
      "ull",  # ultra low latency
      "-rc",
      "vbr",
      "-cq",
      "23",
      "-bf",
      "0",  # Bフレーム無しで並べ替え遅延を避ける
      "-pix_fmt",
      "yuv420p",
      "-g",
      str(gop),
    ]

  return [
    "-c:v",
    "libx264",
    "-preset",
    "ultrafast",
    "-pix_fmt",
    "yuv420p",
    "-g",
    str(gop),
    "-sc_threshold",
    "0",
  ]


def build_ffmpeg_cmd(
  ffmpeg: str,
  *,
  video: str,
  audio: str | None,
  out_dir: Path,
  width: int,
  height: int,
  framerate: int,
  rtbufsize: str,
  hls_time: float,
  duration: float | None,
  nvenc: bool = False,
) -> list[str]:
  """dshow → HLS の ffmpeg コマンドを組み立てる。"""
  playlist = str(out_dir / "index.m3u8")
  segment_pattern = str(out_dir / "seg%05d.ts")

  if audio:
    input_spec = f"video={video}:audio={audio}"
  else:
    input_spec = f"video={video}"

  cmd: list[str] = [
    ffmpeg,
    "-hide_banner",
    "-loglevel",
    "warning",
    "-stats",
    "-f",
    "dshow",
    "-rtbufsize",
    rtbufsize,
    "-framerate",
    str(framerate),
    "-video_size",
    f"{width}x{height}",
    "-i",
    input_spec,
  ]
  cmd += build_video_encode_args(nvenc=nvenc, framerate=framerate, hls_time=hls_time)

  if audio:
    cmd += ["-c:a", "aac", "-b:a", "128k"]
  else:
    cmd += ["-an"]

  if duration is not None and duration > 0:
    cmd += ["-t", str(duration)]

  # list_size 0 = セッション開始からの全断片をプレイリストに残す（任意時点へシーク用）
  # ディスクは時間とともに増える。直近だけなら --hls-window を使う
  cmd += [
    "-f",
    "hls",
    "-hls_time",
    str(hls_time),
    "-hls_list_size",
    "0",
    "-hls_flags",
    "independent_segments+omit_endlist",
    "-hls_segment_filename",
    segment_pattern,
    playlist,
  ]
  return cmd


def build_ffmpeg_cmd_window(
  base_cmd: list[str],
  *,
  hls_window: int,
) -> list[str]:
  """直近 N 断片だけ残す rolling window に差し替える。"""
  # base_cmd 内の -hls_list_size 0 と flags を置換
  out = list(base_cmd)
  try:
    i = out.index("-hls_list_size")
    out[i + 1] = str(hls_window)
  except ValueError:
    pass
  try:
    i = out.index("-hls_flags")
    # delete_segments で古い ts を削除
    out[i + 1] = "independent_segments+omit_endlist+delete_segments"
  except ValueError:
    pass
  return out


def start_http_server(out_dir: Path, port: int) -> ThreadingHTTPServer:
  """out_dir をドキュメントルートに 0.0.0.0:port で待受。"""
  handler = partial(CorsHlsHandler, directory=str(out_dir))
  server = ThreadingHTTPServer(("0.0.0.0", port), handler)
  thread = threading.Thread(target=server.serve_forever, name="hls-http", daemon=True)
  thread.start()
  return server


def print_access_urls(port: int) -> None:
  """iPad 向けに開く URL を表示する。"""
  labels = {
    "lan": "LAN（Wi-Fi 同一ネット向け・推奨）",
    "tailscale": "Tailscale（iPad に VPN/Tailscale があるとき）",
    "virtual": "仮想 NIC（通常は使わない）",
    "other": "その他",
  }
  print()
  print("=== iPad / 他端末では次を開いてください ===")
  print(f"  http://127.0.0.1:{port}/   (この PC のみ)")
  for ip in lan_ipv4_addresses():
    kind = classify_ipv4(ip)
    print(f"  http://{ip}:{port}/   [{labels.get(kind, kind)}]")
  print()
  print("注意:")
  print("  - このスクリプトを動かしたまま iPad で開く（止まっていると読み込みのままになる）")
  print("  - iPad のステータスバーに VPN があるとき、LAN IP が届かないことがある")
  print("    → Tailscale なら 100.x の URL、不要な VPN なら一度オフを試す")
  print("  - 初回は Windows ファイアウォールで TCP 8765 を許可すること")
  print(f"    管理者 PowerShell: python programs/capture_hls/serve_hls.py --open-firewall --port {port}")
  print("停止: Ctrl+C")
  print("==========================================")
  print()


def run_session(args: argparse.Namespace) -> int:
  """ffmpeg と HTTP サーバを起動し、終了まで待つ。"""
  ffmpeg = find_ffmpeg()
  out_dir = Path(args.out_dir).resolve()
  prepare_out_dir(out_dir)

  cmd = build_ffmpeg_cmd(
    ffmpeg,
    video=args.video,
    audio=None if args.no_audio else args.audio,
    out_dir=out_dir,
    width=args.width,
    height=args.height,
    framerate=args.framerate,
    rtbufsize=args.rtbufsize,
    hls_time=args.hls_time,
    duration=args.duration,
    nvenc=args.nvenc,
  )
  if args.hls_window is not None and args.hls_window > 0:
    cmd = build_ffmpeg_cmd_window(cmd, hls_window=args.hls_window)

  print("Output dir:", out_dir)
  print("ffmpeg:", " ".join(cmd))
  print()

  server = start_http_server(out_dir, args.port)
  print_access_urls(args.port)

  # Windows では Ctrl+C で子プロセスも止めやすいよう create 新プロセスグループは使わない
  proc = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    cwd=str(out_dir),
  )

  stop = {"flag": False}

  def _request_stop(*_args: object) -> None:
    stop["flag"] = True

  # SIGINT / SIGTERM
  signal.signal(signal.SIGINT, _request_stop)
  if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _request_stop)

  try:
    while True:
      if stop["flag"]:
        break
      code = proc.poll()
      if code is not None:
        print(f"ffmpeg exited with code {code}")
        break
      time.sleep(0.2)
  finally:
    # 優雅終了: ffmpeg に q を送る（効かない場合は terminate）
    if proc.poll() is None:
      try:
        if proc.stdin:
          proc.stdin.write(b"q")
          proc.stdin.flush()
      except OSError:
        pass
      try:
        proc.wait(timeout=5)
      except subprocess.TimeoutExpired:
        proc.terminate()
        try:
          proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
          proc.kill()
    server.shutdown()

  print("Stopped.")
  return 0


def main() -> int:
  parser = argparse.ArgumentParser(
    description="Capture device to HLS + LAN HTTP server (iPad viewer)."
  )
  parser.add_argument(
    "--list",
    action="store_true",
    help="List DirectShow devices via ffmpeg and exit.",
  )
  parser.add_argument(
    "--video",
    default=DEFAULT_VIDEO,
    help=f'DirectShow video device name (default: "{DEFAULT_VIDEO}").',
  )
  parser.add_argument(
    "--audio",
    default=DEFAULT_AUDIO,
    help=f'DirectShow audio device name (default: "{DEFAULT_AUDIO}").',
  )
  parser.add_argument(
    "--no-audio",
    action="store_true",
    help="Record video only (no audio track).",
  )
  parser.add_argument(
    "--out-dir",
    default=str(DEFAULT_OUT_DIR),
    help="Directory for HLS segments and viewer (default: programs/capture_hls/out).",
  )
  parser.add_argument(
    "--port",
    type=int,
    default=8765,
    help="HTTP listen port (default: 8765).",
  )
  parser.add_argument("--width", type=int, default=1920, help="Capture width.")
  parser.add_argument("--height", type=int, default=1080, help="Capture height.")
  parser.add_argument("--framerate", type=int, default=60, help="Capture framerate.")
  parser.add_argument(
    "--rtbufsize",
    default="100M",
    help="dshow real-time buffer size (default: 100M).",
  )
  parser.add_argument(
    "--hls-time",
    type=float,
    default=1.0,
    help="HLS segment duration in seconds (default: 1).",
  )
  parser.add_argument(
    "--nvenc",
    action="store_true",
    help="Use NVIDIA NVENC (h264_nvenc) instead of libx264.",
  )
  parser.add_argument(
    "--hls-window",
    type=int,
    default=None,
    help="If set, keep only this many recent segments (rolling DVR). Default: keep all.",
  )
  parser.add_argument(
    "--duration",
    type=float,
    default=None,
    help="Stop after N seconds (omit to run until Ctrl+C).",
  )
  parser.add_argument(
    "--open-firewall",
    action="store_true",
    help="Add Windows inbound allow rule for --port and exit (run as Administrator).",
  )
  args = parser.parse_args()

  if args.open_firewall:
    ensure_firewall_rule(args.port)
    return 0

  if args.list:
    try:
      return list_dshow_devices(find_ffmpeg())
    except RuntimeError as e:
      print(e, file=sys.stderr)
      return 1

  if not VIEWER_HTML.is_file():
    print(f"viewer.html not found: {VIEWER_HTML}", file=sys.stderr)
    return 1

  try:
    return run_session(args)
  except RuntimeError as e:
    print(e, file=sys.stderr)
    return 1
  except OSError as e:
    # ポート使用中など
    print(f"Server/OS error: {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
