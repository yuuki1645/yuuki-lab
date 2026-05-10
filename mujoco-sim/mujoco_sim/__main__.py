"""Run the HTTP API: python -m mujoco_sim [--no-viewer] ..."""

from __future__ import annotations

import argparse
import logging
import os
import threading


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
        "--no-viewer",
        action="store_true",
        help="パッシブ Viewer を出さず HTTP のみ（GUI なし・ヘッドレス）",
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
    from mujoco_sim.core import Simulation
    from mujoco_sim.passive_viewer import run_passive_viewer_follow_sim

    if args.no_viewer:
        app = create_app()
        app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)
        return

    sim = Simulation()
    app = create_app(simulation=sim)

    def run_flask() -> None:
        app.run(
            host=args.host,
            port=args.port,
            threaded=True,
            use_reloader=False,
        )

    thread = threading.Thread(target=run_flask, daemon=True)
    thread.start()
    run_passive_viewer_follow_sim(sim)


if __name__ == "__main__":
    main()
