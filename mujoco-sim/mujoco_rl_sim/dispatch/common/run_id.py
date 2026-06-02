"""run_id の生成と検証。"""

from __future__ import annotations

import re

_RUN_ID_RE = re.compile(r"^(.+)_s(\d+)_r(\d+)$")


def build_run_id(*, sweep_id: str, seed: int, run_index: int) -> str:
  if not sweep_id:
    raise ValueError("sweep_id が空です")
  if seed < 0:
    raise ValueError("seed は 0 以上")
  if run_index < 0:
    raise ValueError("run_index は 0 以上")
  return f"{sweep_id}_s{seed}_r{run_index}"


def parse_run_id_parts(run_id: str) -> tuple[str, int, int]:
  m = _RUN_ID_RE.match(run_id)
  if not m:
    raise ValueError(f"run_id 形式が不正です: {run_id!r} (期待: <sweep_id>_s<seed>_r<index>)")
  return m.group(1), int(m.group(2)), int(m.group(3))
