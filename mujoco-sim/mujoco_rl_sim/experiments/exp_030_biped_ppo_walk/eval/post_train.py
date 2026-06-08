"""学習終了後の自動 eval（train → eval_report.json）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eval.report import build_eval_report, write_eval_report
from eval.runner import run_checkpoint_eval
from eval.spec import EPISODES_PER_SEED, EVAL_SEEDS, PRIMARY_METRIC_NAME


def run_post_train_eval(
  checkpoint_path: Path,
  *,
  device: str = "cpu",
  out_path: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
  """``final.pt`` 等に対して eval を実行し ``eval_report.json`` を書き出す。

  Args:
    out_path: 省略時は ``<checkpoint 親>/eval_report.json``。

  Returns:
    (書き出した ``eval_report.json`` のパス, report dict)
  """
  ckpt = checkpoint_path.resolve()
  if not ckpt.is_file():
    raise FileNotFoundError(f"post-train eval: checkpoint not found: {ckpt}")

  out_path = (out_path or (ckpt.parent / "eval_report.json")).resolve()
  print(
    f"[eval] post-train: checkpoint={ckpt}\n"
    f"[eval] trials={len(EVAL_SEEDS)} seeds × {EPISODES_PER_SEED} ep "
    f"= {len(EVAL_SEEDS) * EPISODES_PER_SEED}"
  )

  records = run_checkpoint_eval(ckpt, device=device)
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
    f"[eval] truncated_rate={report['summary']['metrics']['truncated_rate']:.3f}"
  )
  return out_path, report
