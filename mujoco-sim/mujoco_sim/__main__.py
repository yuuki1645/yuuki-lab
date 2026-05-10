"""Run the HTTP API: python -m mujoco_sim [--host] [--port] [--xml PATH]."""

from __future__ import annotations

import argparse
import logging
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="MuJoCo simulation HTTP server (Flask)")
    # 0.0.0.0: LAN の他端末から robotics-hub 経由で叩けるようにする（127.0.0.1 のみだと同一 PC 以外から届かない）
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--xml",
        default=None,
        help="Path to main MJCF file (sets MUJOCO_SIM_XML for this process)",
    )
    parser.add_argument(
        "--quiet-http",
        action="store_true",
        help="Werkzeug の HTTP アクセス行を抑える（mujoco_sim.api の行は出る）",
    )
    args = parser.parse_args()
    if args.xml:
        os.environ["MUJOCO_SIM_XML"] = args.xml

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.quiet_http:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    from mujoco_sim.app import create_app

    app = create_app()
    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
