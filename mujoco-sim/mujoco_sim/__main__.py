"""Run the HTTP API: python -m mujoco_sim [--host] [--port] [--xml PATH]."""

from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="MuJoCo simulation HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--xml",
        default=None,
        help="Path to main MJCF file (sets MUJOCO_SIM_XML for this process)",
    )
    args = parser.parse_args()
    if args.xml:
        os.environ["MUJOCO_SIM_XML"] = args.xml

    uvicorn.run(
        "mujoco_sim.app:app",
        host=args.host,
        port=args.port,
        factory=False,
    )


if __name__ == "__main__":
    main()
