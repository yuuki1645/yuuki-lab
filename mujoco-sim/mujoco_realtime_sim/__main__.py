"""Run the HTTP API: python -m mujoco_realtime_sim [--no-viewer] ..."""

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
        help="Path to main MJCF file (sets MUJOCO_REALTIME_SIM_XML for this process)",
    )
    parser.add_argument(
        "--no-viewer",
        action="store_true",
        help="パッシブ Viewer を出さず HTTP のみ（GUI なし・ヘッドレス）",
    )
    parser.add_argument(
        "--no-auto-step",
        action="store_true",
        help="サーバー側の常時 mj_step（実時間ペース）を行わない",
    )
    parser.add_argument(
        "--quiet-http",
        action="store_true",
        help="Werkzeug の HTTP アクセス行を抑える（mujoco_realtime_sim.api の行は出る）",
    )
    args = parser.parse_args()
    if args.xml:
        os.environ["MUJOCO_REALTIME_SIM_XML"] = args.xml
        os.environ["MUJOCO_SIM_XML"] = args.xml

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.quiet_http:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    from mujoco_realtime_sim.app import create_app
    from mujoco_realtime_sim.core import Simulation
    from mujoco_realtime_sim.passive_viewer import run_passive_viewer_follow_sim
    from mujoco_realtime_sim.realtime import RealtimeStepper

    sim = Simulation()
    stepper: RealtimeStepper | None = None
    if not args.no_auto_step:
        stepper = RealtimeStepper(sim)
        stepper.start()

    app = create_app(simulation=sim, stepper=stepper)

    def run_flask() -> None:
        app.run(
            host=args.host,
            port=args.port,
            threaded=True,
            use_reloader=False,
        )

    if args.no_viewer:
        # ヘッドレス: メインスレッドで Flask を回す。
        run_flask()
        return

    thread = threading.Thread(target=run_flask, daemon=True)
    thread.start()
    run_passive_viewer_follow_sim(sim)


if __name__ == "__main__":
    main()
