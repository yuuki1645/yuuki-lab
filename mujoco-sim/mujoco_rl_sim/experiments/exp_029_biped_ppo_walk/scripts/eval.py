"""学習済みチェックポイントの公式評価（eval_report.json を出力）。

仕様の正本: README「評価仕様」節、``eval/spec.py``。
デバッグ用の時系列・フレーム保存は ``scripts/analyze_rollout.py`` を使用する。
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
  sys.path.insert(0, str(_ROOT))

from _paths import install

install()

import argparse

from eval.post_train import run_post_train_eval
import rl.checkpoint as checkpoint


def _parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(description=__doc__)
  p.add_argument(
    "--checkpoint",
    type=str,
    required=True,
    help="評価する .pt（runs/<exp>/<run>/final.pt 等）",
  )
  p.add_argument(
    "--out",
    type=str,
    default=None,
    help="出力 JSON（省略時は <checkpoint 親>/eval_report.json）",
  )
  p.add_argument("--device", type=str, default="cpu")
  return p.parse_args()


def main() -> None:
  args = _parse_args()
  ckpt = checkpoint.resolve_checkpoint_path(args.checkpoint)
  out_path = Path(args.out).expanduser().resolve() if args.out else None
  run_post_train_eval(ckpt, device=args.device, out_path=out_path)


if __name__ == "__main__":
  main()
