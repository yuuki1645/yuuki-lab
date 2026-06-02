"""Coordinator サーバー起動。"""

from __future__ import annotations

import argparse

from mujoco_rl_sim.dispatch.coordinator.app import create_app
from mujoco_rl_sim.dispatch.coordinator.settings import load_coordinator_settings


def main() -> None:
  p = argparse.ArgumentParser(description="MuJoCo RL dispatch Coordinator")
  p.add_argument("--config", type=str, default=None, help="coordinator.config.toml")
  args = p.parse_args()
  from pathlib import Path

  cfg_path = Path(args.config) if args.config else None
  settings = load_coordinator_settings(cfg_path)
  app = create_app(settings)
  print(f"[dispatch] Coordinator http://{settings.host}:{settings.port} db={settings.db_path}")
  app.run(host=settings.host, port=settings.port, threaded=True)


if __name__ == "__main__":
  main()
