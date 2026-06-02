"""dispatch CLI（sweep 登録・確認）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mujoco_rl_sim.dispatch.coordinator.db.connection import connect
from mujoco_rl_sim.dispatch.coordinator.db.repository import DispatchRepository
from mujoco_rl_sim.dispatch.coordinator.services.sweep_register import plan_sweep_file, register_sweep_file
from mujoco_rl_sim.dispatch.coordinator.settings import load_coordinator_settings


def main(argv: list[str] | None = None) -> None:
  parser = argparse.ArgumentParser(prog="mujoco-dispatch", description="分散実験 dispatch CLI")
  parser.add_argument("--config", type=Path, default=None, help="Coordinator TOML")
  sub = parser.add_subparsers(dest="cmd", required=True)

  p_plan = sub.add_parser("plan", help="sweep YAML からジョブ数を表示（DB未使用）")
  p_plan.add_argument("--file", type=Path, required=True)

  p_reg = sub.add_parser("sweep", help="sweep 操作")
  reg_sub = p_reg.add_subparsers(dest="sweep_cmd", required=True)
  p_register = reg_sub.add_parser("register", help="sweep を DB に登録")
  p_register.add_argument("--file", type=Path, required=True)

  p_status = reg_sub.add_parser("status", help="sweep 状態")
  p_status.add_argument("--sweep-id", type=str, required=True)

  args = parser.parse_args(argv)

  if args.cmd == "plan":
    info = plan_sweep_file(args.file.resolve())
    print(f"sweep_id: {info['sweep_id']}")
    print(f"exp_id:   {info['exp_id']}")
    print(f"jobs:     {info['job_count']}")
    print(f"shuffle:  {info['shuffle_seed']}")
    for rid in info["first_jobs"]:
      print(f"  - {rid}")
    return

  settings = load_coordinator_settings(args.config)
  repo = DispatchRepository(connect(settings.db_path))

  if args.cmd == "sweep" and args.sweep_cmd == "register":
    info = register_sweep_file(repo, args.file.resolve())
    print(f"registered {info['jobs_registered']} jobs for sweep {info['sweep_id']}")
    return

  if args.cmd == "sweep" and args.sweep_cmd == "status":
    sweeps = [s for s in repo.list_sweeps() if s["sweep_id"] == args.sweep_id]
    if not sweeps:
      print(f"sweep not found: {args.sweep_id}", file=sys.stderr)
      sys.exit(1)
    s = sweeps[0]
    print(
      f"{s['sweep_id']}: queued={s['queued']} running={s['running']} "
      f"ok={s['succeeded']} fail={s['failed']} cancelled={s['cancelled']}"
    )
    return

  parser.error("unknown command")


if __name__ == "__main__":
  main()
