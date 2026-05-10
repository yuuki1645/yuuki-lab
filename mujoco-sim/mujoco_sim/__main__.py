"""Run the HTTP API: python -m mujoco_sim [--host] [--port] [--xml PATH]."""

from __future__ import annotations

import argparse
import logging
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="MuJoCo simulation HTTP server (Flask)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--xml",
        default=None,
        help="Path to main MJCF file (sets MUJOCO_SIM_XML for this process)",
    )
    parser.add_argument(
        "--access-log",
        action="store_true",
        help="Show Werkzeug HTTP access logs (default: errors only).",
    )
    args = parser.parse_args()
    if args.xml:
        os.environ["MUJOCO_SIM_XML"] = args.xml

    if not args.access_log:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    from mujoco_sim.app import create_app

    app = create_app()
    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
