"""Worker 起動。"""

from __future__ import annotations

import argparse
from pathlib import Path

from mujoco_rl_sim.dispatch.worker.agent import WorkerAgent
from mujoco_rl_sim.dispatch.worker.settings import load_worker_settings


def main() -> None:
  p = argparse.ArgumentParser(description="MuJoCo RL dispatch Worker")
  p.add_argument(
    "--config",
    type=Path,
    required=True,
    help="worker.config.toml（各端末のローカル設定）",
  )
  args = p.parse_args()
  settings = load_worker_settings(args.config.resolve())
  WorkerAgent(settings).run_forever()


if __name__ == "__main__":
  main()
