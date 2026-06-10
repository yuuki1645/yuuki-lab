"""run サマリを表示（AI 分析用）。"""

from __future__ import annotations

from _paths import install

install()

import argparse
import json
from pathlib import Path


def main() -> None:
  p = argparse.ArgumentParser(description="walk_v0 run の summary / incidents を表示")
  p.add_argument("--run-dir", type=str, required=True)
  args = p.parse_args()
  run_dir = Path(args.run_dir)
  summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
  print("=== summary ===")
  print(json.dumps(summary, ensure_ascii=False, indent=2))
  inc_path = run_dir / "incidents.json"
  if inc_path.is_file():
    incidents = json.loads(inc_path.read_text(encoding="utf-8"))
    print(f"\n=== incidents ({len(incidents)}) ===")
    print(json.dumps(incidents, ensure_ascii=False, indent=2))


if __name__ == "__main__":
  main()
