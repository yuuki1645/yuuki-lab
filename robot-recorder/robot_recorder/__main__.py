"""python -m robot_recorder の入口。"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

# Windows cp932 対策
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32" and hasattr(sys.stderr, "reconfigure"):
  sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# パッケージ親を path に（python -m 以外の起動にも耐える）
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
  sys.path.insert(0, str(_ROOT))

from robot_recorder.app import RecorderApp
from robot_recorder.config import load_config
from robot_recorder.server import run_server


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="yuuki-lab robot-recorder")
  parser.add_argument(
    "--config",
    type=Path,
    default=None,
    help="設定 YAML（省略時は config.local.yaml / example）",
  )
  parser.add_argument("--host", default=None)
  parser.add_argument("--port", type=int, default=None)
  args = parser.parse_args(argv)

  cfg = load_config(args.config)
  if args.host:
    cfg.host = args.host
  if args.port:
    cfg.port = args.port

  app = RecorderApp(cfg)
  app.start_background()
  httpd = run_server(app, cfg.host, cfg.port)

  def _shutdown(*_args: object) -> None:
    print("Shutting down...")
    app.stop()
    httpd.shutdown()

  signal.signal(signal.SIGINT, _shutdown)
  if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _shutdown)

  print("=== robot-recorder ===")
  print(f"  data_root: {cfg.data_root}")
  print(f"  http://127.0.0.1:{cfg.port}/")
  print(f"  MJPEG:     http://127.0.0.1:{cfg.port}/stream.mjpg")
  print(f"  burn_timestamp: {cfg.capture.burn_timestamp}")
  try:
    httpd.serve_forever()
  finally:
    app.stop()
    httpd.server_close()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
