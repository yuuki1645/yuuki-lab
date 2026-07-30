"""robot-recorder 起動用（cwd に依存しにくい）。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
  sys.path.insert(0, str(_ROOT))

from robot_recorder.__main__ import main

if __name__ == "__main__":
  raise SystemExit(main())
