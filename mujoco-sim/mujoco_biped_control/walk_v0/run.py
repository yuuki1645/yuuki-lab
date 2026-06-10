"""制御走行のエントリポイント（ヘッドレス・ログ出力）。"""

from __future__ import annotations

from _paths import install

install()

import argparse
import json
from pathlib import Path

from runtime.config import load_run_config
from runtime.session import run_session
from walk_meta import RUNS_ROOT


def main() -> None:
  p = argparse.ArgumentParser(description="walk_v0: 明示制御で MuJoCo 歩行テスト（ログ・incident 記録）")
  p.add_argument(
    "--config",
    type=str,
    default="conf/default.yaml",
    help="run 設定 YAML",
  )
  p.add_argument(
    "--run-dir",
    type=str,
    default=None,
    help="出力先（省略時は runs/mujoco_biped_control/walk_v0/run_* 自動生成）",
  )
  args = p.parse_args()

  cfg_path = Path(args.config)
  if not cfg_path.is_absolute():
    cfg_path = Path(__file__).resolve().parent / cfg_path

  run_cfg = load_run_config(cfg_path)
  out_dir = Path(args.run_dir) if args.run_dir else None

  result = run_session(run_cfg, enable_viewer=False, visualize=False, run_dir=out_dir)
  print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
  print(f"run_dir: {result['run_dir']}")
  print(f"runs root: {RUNS_ROOT}")


if __name__ == "__main__":
  main()
