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

from eval.report import build_eval_report, write_eval_report
from eval.runner import run_checkpoint_eval
from eval.spec import EPISODES_PER_SEED, EVAL_SEEDS, PRIMARY_METRIC_NAME
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
  out_path = (
    Path(args.out).expanduser().resolve()
    if args.out
    else (ckpt.parent / "eval_report.json")
  )

  print(
    f"[eval] checkpoint={ckpt}\n"
    f"[eval] trials={len(EVAL_SEEDS)} seeds × {EPISODES_PER_SEED} ep "
    f"= {len(EVAL_SEEDS) * EPISODES_PER_SEED}"
  )

  records = run_checkpoint_eval(ckpt, device=args.device)
  report = build_eval_report(checkpoint_path=ckpt, records=records)
  write_eval_report(out_path, report)

  disp = report["summary"]["metrics"]["displacement_x"]
  print(f"[eval] wrote: {out_path}")
  print(
    f"[eval] {PRIMARY_METRIC_NAME}={disp['mean']:.4f} m "
    f"(std={disp['std']:.4f}, min={disp['min']:.4f}, max={disp['max']:.4f}, "
    f"95%CI=[{disp['ci95_low']:.4f}, {disp['ci95_high']:.4f}])"
  )
  print(
    f"[eval] truncated_rate="
    f"{report['summary']['metrics']['truncated_rate']:.3f}"
  )


if __name__ == "__main__":
  main()
