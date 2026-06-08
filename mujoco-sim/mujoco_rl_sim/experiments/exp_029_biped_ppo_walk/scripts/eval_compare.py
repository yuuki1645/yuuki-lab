"""複数 run の eval_report.json を横断比較する CLI。

``runs/<exp>/<run>/eval_report.json`` を読み、主指標で並べ替えて表表示する。
仕様の正本: README「評価仕様」節、``eval/spec.py``。
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

from eval.compare import (
  build_compare_result,
  discover_reports_in_runs_dir,
  format_compare_table,
  resolve_report_paths,
  write_compare_csv,
)
from eval.spec import EVAL_SPEC_ID
from package_meta import CHECKPOINT_ROOT


def _parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(description=__doc__)
  p.add_argument(
    "targets",
    nargs="*",
    type=str,
    help="eval_report.json または run ディレクトリ（省略時は --runs-dir を走査）",
  )
  p.add_argument(
    "--runs-dir",
    type=str,
    default=None,
    help=f"run 親ディレクトリ（省略時: {CHECKPOINT_ROOT}）",
  )
  p.add_argument(
    "--csv",
    type=str,
    default=None,
    help="比較結果を CSV で書き出すパス",
  )
  p.add_argument(
    "--expected-spec-id",
    type=str,
    default=EVAL_SPEC_ID,
    help=f"期待する eval_spec_id（不一致は警告。既定: {EVAL_SPEC_ID}）",
  )
  return p.parse_args()


def _collect_report_paths(args: argparse.Namespace) -> tuple[int, list[Path]]:
  """位置引数または --runs-dir から eval_report パス一覧を得る。"""
  if args.targets:
    paths = resolve_report_paths(Path(t) for t in args.targets)
    # 位置引数指定時は走査数 = 指定した run 数（情報表示用）
    return len(paths), paths

  runs_dir = Path(args.runs_dir or CHECKPOINT_ROOT).expanduser()
  return discover_reports_in_runs_dir(runs_dir)


def main() -> None:
  args = _parse_args()
  runs_scanned, report_paths = _collect_report_paths(args)

  print(
    f"[compare] scanned {runs_scanned} run dir(s), "
    f"{len(report_paths)} with eval_report.json"
  )

  if not report_paths:
    print("[compare] 比較対象がありません（eval_report.json がある run が必要です）")
    raise SystemExit(1)

  result = build_compare_result(
    report_paths,
    runs_scanned=runs_scanned,
    expected_spec_id=args.expected_spec_id,
  )

  if result.mismatched_specs:
    specs = ", ".join(result.mismatched_specs)
    print(
      f"[compare] warning: eval_spec_id mismatch "
      f"(expected {args.expected_spec_id!r}, found: {specs})"
    )

  print()
  print(format_compare_table(result.rows))

  if args.csv:
    out = write_compare_csv(Path(args.csv), result.rows)
    print(f"[compare] wrote CSV -> {out}")


if __name__ == "__main__":
  main()
