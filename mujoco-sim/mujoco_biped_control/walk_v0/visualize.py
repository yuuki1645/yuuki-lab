"""制御走行を MuJoCo viewer で実時間再生。"""

from __future__ import annotations

from _paths import install

install()

import argparse
import json
from pathlib import Path

from runtime.config import load_run_config
from runtime.session import run_session


def main() -> None:
  p = argparse.ArgumentParser(description="walk_v0: 制御走行をビューア付きで実行")
  p.add_argument("--config", type=str, default="conf/default.yaml")
  p.add_argument("--run-dir", type=str, default=None, help="ログ保存先（省略可）")
  p.add_argument(
    "--no-log",
    action="store_true",
    help="runs/ へのログ保存をスキップ（run-dir 未指定時）",
  )
  args = p.parse_args()

  cfg_path = Path(args.config)
  if not cfg_path.is_absolute():
    cfg_path = Path(__file__).resolve().parent / cfg_path

  run_cfg = load_run_config(cfg_path)
  out_dir = None
  if args.run_dir:
    out_dir = Path(args.run_dir)
  elif not args.no_log:
    out_dir = None  # 自動生成

  if args.no_log and not args.run_dir:
    # ログなしの場合は一時 run を作らず… session は run_dir 必須なので temp
    import tempfile

    out_dir = Path(tempfile.mkdtemp(prefix="walk_v0_vis_"))

  result = run_session(
    run_cfg,
    enable_viewer=True,
    visualize=True,
    run_dir=out_dir,
  )
  print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
  if not args.no_log or args.run_dir:
    print(f"run_dir: {result['run_dir']}")


if __name__ == "__main__":
  main()
