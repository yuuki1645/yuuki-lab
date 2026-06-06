"""eval_report.json の横断比較（読み込み・集約・ソート・表示用データ）。"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from eval.spec import EVAL_SPEC_ID, PRIMARY_METRIC_NAME

# eval_report.json のファイル名（run ディレクトリ直下）
_EVAL_REPORT_FILENAME = "eval_report.json"


@dataclass(frozen=True)
class EvalCompareRow:
  """比較表の 1 行分。"""

  run_name: str
  report_path: Path
  eval_spec_id: str
  spec_mismatch: bool
  primary_metric_name: str
  primary_metric_value: float
  displacement_x_mean: float
  ci95_low: float
  ci95_high: float
  episode_length_mean: float
  truncated_rate: float
  checkpoint_name: str
  created_at_utc: str
  git_commit_short: str


@dataclass(frozen=True)
class EvalCompareResult:
  """スキャン結果と比較行のまとめ。"""

  runs_scanned: int
  reports_found: int
  rows: tuple[EvalCompareRow, ...]
  mismatched_specs: tuple[str, ...]


def _short_git(commit: str | None) -> str:
  """git commit を 7 文字に短縮（無ければ ``-``）。"""
  if not commit:
    return "-"
  text = str(commit).strip()
  return text[:7] if text else "-"


def _metric_block(report: dict[str, Any], key: str) -> dict[str, float]:
  """``summary.metrics.<key>`` を取得（欠損時は 0 埋め）。"""
  summary = report.get("summary") or {}
  metrics = summary.get("metrics") or {}
  block = metrics.get(key) or {}
  return {
    "mean": float(block.get("mean", 0.0)),
    "ci95_low": float(block.get("ci95_low", 0.0)),
    "ci95_high": float(block.get("ci95_high", 0.0)),
  }


def load_eval_report(path: Path) -> dict[str, Any]:
  """``eval_report.json`` を読み込む。"""
  resolved = path.resolve()
  try:
    data = json.loads(resolved.read_text(encoding="utf-8"))
  except OSError as exc:
    raise OSError(f"eval_report の読み込みに失敗: {resolved}") from exc
  except json.JSONDecodeError as exc:
    raise ValueError(f"eval_report の JSON が不正: {resolved}") from exc
  if not isinstance(data, dict):
    raise ValueError(f"eval_report のルートは object である必要があります: {resolved}")
  return data


def parse_compare_row(
  report_path: Path,
  report: dict[str, Any],
  *,
  expected_spec_id: str = EVAL_SPEC_ID,
) -> EvalCompareRow:
  """1 件の eval_report から比較行を組み立てる。"""
  disp = _metric_block(report, "displacement_x")
  ep_len = _metric_block(report, "episode_length")
  summary = report.get("summary") or {}
  metrics = summary.get("metrics") or {}

  eval_spec_id = str(report.get("eval_spec_id") or "")
  primary_name = str(
    report.get("primary_metric_name")
    or summary.get("primary_metric_name")
    or PRIMARY_METRIC_NAME
  )
  primary_value = float(
    report.get("primary_metric_value")
    if report.get("primary_metric_value") is not None
    else summary.get("primary_metric_value", disp["mean"])
  )

  checkpoint_raw = str(report.get("checkpoint") or "")
  checkpoint_name = Path(checkpoint_raw).name if checkpoint_raw else "-"

  return EvalCompareRow(
    run_name=report_path.resolve().parent.name,
    report_path=report_path.resolve(),
    eval_spec_id=eval_spec_id,
    spec_mismatch=bool(eval_spec_id and eval_spec_id != expected_spec_id),
    primary_metric_name=primary_name,
    primary_metric_value=primary_value,
    displacement_x_mean=disp["mean"],
    ci95_low=disp["ci95_low"],
    ci95_high=disp["ci95_high"],
    episode_length_mean=ep_len["mean"],
    truncated_rate=float(metrics.get("truncated_rate", 0.0)),
    checkpoint_name=checkpoint_name or "-",
    created_at_utc=str(report.get("created_at_utc") or ""),
    git_commit_short=_short_git(report.get("git_commit")),
  )


def discover_reports_in_runs_dir(runs_dir: Path) -> tuple[int, list[Path]]:
  """``runs_dir/<run>/eval_report.json`` を探索する。

  Returns:
    (走査した run ディレクトリ数, 見つかった eval_report パスのリスト)
  """
  base = runs_dir.resolve()
  if not base.is_dir():
    raise NotADirectoryError(f"runs ディレクトリが存在しません: {base}")

  run_dirs = sorted(p for p in base.iterdir() if p.is_dir())
  reports: list[Path] = []
  for run_dir in run_dirs:
    candidate = run_dir / _EVAL_REPORT_FILENAME
    if candidate.is_file():
      reports.append(candidate)
  return len(run_dirs), reports


def resolve_report_paths(targets: Sequence[Path]) -> list[Path]:
  """CLI 位置引数から eval_report パスを解決する。"""
  resolved: list[Path] = []
  seen: set[Path] = set()

  for raw in targets:
    path = raw.expanduser().resolve()
    if path.is_file():
      report = path
    elif path.is_dir():
      report = path / _EVAL_REPORT_FILENAME
      if not report.is_file():
        raise FileNotFoundError(
          f"eval_report.json が見つかりません: {path / _EVAL_REPORT_FILENAME}"
        )
    else:
      raise FileNotFoundError(f"パスが存在しません: {path}")

    key = report.resolve()
    if key not in seen:
      seen.add(key)
      resolved.append(key)
  return resolved


def sort_compare_rows(rows: Sequence[EvalCompareRow]) -> tuple[EvalCompareRow, ...]:
  """主指標降順 → eval 実施時刻降順で並べ替える。"""

  def _sort_key(row: EvalCompareRow) -> tuple[float, str]:
    # created_at_utc は ISO 文字列なので辞書順 ≒ 時系列
    return (row.primary_metric_value, row.created_at_utc)

  return tuple(sorted(rows, key=_sort_key, reverse=True))


def build_compare_result(
  report_paths: Sequence[Path],
  *,
  runs_scanned: int,
  expected_spec_id: str = EVAL_SPEC_ID,
) -> EvalCompareResult:
  """複数 eval_report を読み込み、ソート済み結果を返す。"""
  rows: list[EvalCompareRow] = []
  mismatched: set[str] = set()

  for report_path in report_paths:
    report = load_eval_report(report_path)
    row = parse_compare_row(
      report_path,
      report,
      expected_spec_id=expected_spec_id,
    )
    rows.append(row)
    if row.spec_mismatch:
      mismatched.add(row.eval_spec_id)

  return EvalCompareResult(
    runs_scanned=runs_scanned,
    reports_found=len(report_paths),
    rows=sort_compare_rows(rows),
    mismatched_specs=tuple(sorted(mismatched)),
  )


def _parse_created_at_short(iso_text: str) -> str:
  """ISO 時刻を表示用に短縮（失敗時は原文の先頭）。"""
  text = iso_text.strip()
  if not text:
    return "-"
  try:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M")
  except ValueError:
    return text[:16] if len(text) > 16 else text


def _format_ci(row: EvalCompareRow) -> str:
  return f"[{row.ci95_low:+.3f},{row.ci95_high:+.3f}]"


# ターミナル表の列定義（ヘッダ, 幅, 値フォーマット）
_TABLE_COLUMNS: tuple[tuple[str, int, str], ...] = (
  ("run", 28, "run_name"),
  ("disp_x", 8, "displacement_x_mean"),
  ("ci95", 19, "ci"),
  ("ep_len", 7, "episode_length_mean"),
  ("trunc", 6, "truncated_rate"),
  ("ckpt", 12, "checkpoint_name"),
  ("eval_at", 16, "eval_at"),
  ("git", 7, "git_commit_short"),
  ("!", 1, "spec_flag"),
)


def _cell_value(row: EvalCompareRow, field: str, *, is_best: bool) -> str:
  """1 セルの表示文字列。"""
  prefix = "*" if is_best else " "
  if field == "run_name":
    return f"{prefix}{row.run_name}"
  if field == "ci":
    return _format_ci(row)
  if field == "displacement_x_mean":
    return f"{row.displacement_x_mean:+.4f}"
  if field == "episode_length_mean":
    return f"{row.episode_length_mean:.1f}"
  if field == "truncated_rate":
    return f"{row.truncated_rate:.3f}"
  if field == "eval_at":
    return _parse_created_at_short(row.created_at_utc)
  if field == "spec_flag":
    return "!" if row.spec_mismatch else ""
  return str(getattr(row, field))


def format_compare_table(rows: Sequence[EvalCompareRow]) -> str:
  """固定幅の比較表を文字列で返す。"""
  if not rows:
    return "(eval_report.json がありません)"

  headers = [col[0] for col in _TABLE_COLUMNS]
  widths = [col[1] for col in _TABLE_COLUMNS]
  fields = [col[2] for col in _TABLE_COLUMNS]

  header_line = " ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
  divider = " ".join("-" * w for w in widths)

  body_lines: list[str] = []
  for index, row in enumerate(rows):
    cells = [
      _cell_value(row, field, is_best=(index == 0)).ljust(width)[:width]
      for (_, width, field) in _TABLE_COLUMNS
    ]
    body_lines.append(" ".join(cells))

  legend = "* = best (primary metric desc)"
  return "\n".join([header_line, divider, *body_lines, "", legend])


def write_compare_csv(path: Path, rows: Sequence[EvalCompareRow]) -> Path:
  """比較結果を CSV で書き出す。"""
  out = path.expanduser().resolve()
  out.parent.mkdir(parents=True, exist_ok=True)

  fieldnames = [
    "rank",
    "run_name",
    "primary_metric_name",
    "primary_metric_value",
    "displacement_x_mean",
    "ci95_low",
    "ci95_high",
    "episode_length_mean",
    "truncated_rate",
    "checkpoint_name",
    "created_at_utc",
    "git_commit_short",
    "eval_spec_id",
    "spec_mismatch",
    "report_path",
  ]

  with out.open("w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    for rank, row in enumerate(rows, start=1):
      writer.writerow(
        {
          "rank": rank,
          "run_name": row.run_name,
          "primary_metric_name": row.primary_metric_name,
          "primary_metric_value": row.primary_metric_value,
          "displacement_x_mean": row.displacement_x_mean,
          "ci95_low": row.ci95_low,
          "ci95_high": row.ci95_high,
          "episode_length_mean": row.episode_length_mean,
          "truncated_rate": row.truncated_rate,
          "checkpoint_name": row.checkpoint_name,
          "created_at_utc": row.created_at_utc,
          "git_commit_short": row.git_commit_short,
          "eval_spec_id": row.eval_spec_id,
          "spec_mismatch": row.spec_mismatch,
          "report_path": str(row.report_path),
        }
      )
  return out
