"""atom-rt からの入口。実体は link/py/experiment_log.py。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# atom-rt/tools/lib からリポジトリ直下の link/py を読む。
_CANON = Path(__file__).resolve().parents[3] / "link" / "py" / "experiment_log.py"
_spec = importlib.util.spec_from_file_location("link_experiment_log", _CANON)
if _spec is None or _spec.loader is None:
    raise ImportError(f"実験記録が見つかりません: {_CANON}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["link_experiment_log"] = _mod
_spec.loader.exec_module(_mod)

for _name, _value in vars(_mod).items():
    if _name.startswith("__"):
        continue
    globals()[_name] = _value
