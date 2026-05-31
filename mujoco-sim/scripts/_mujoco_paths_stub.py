"""実験フォルダ基準のパス解決（スタンドアロン用）。"""

from pathlib import Path

from package_meta import EXP_DIR


def exp_path(*parts: str) -> str:
  return str(EXP_DIR.joinpath(*parts))
