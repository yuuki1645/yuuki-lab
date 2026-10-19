"""robot_description/model_size.py の寸法を、学習パッケージから読む。

yaml が正本。ここには数値を書かない。股の間隔や足裏高さを変えるときは yaml を直し、
generate_urdf.py で URDF を作り直す。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# yuuki_legs → robots → assets → パッケージ → 拡張 → source → isaac-lab → リポジトリ。
_PATH = Path(__file__).resolve().parents[7] / "robot_description" / "model_size.py"
_spec = importlib.util.spec_from_file_location("yuuki_robot_model_size", _PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"寸法モジュールがありません: {_PATH}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

# 股ロール軸から足首ロール軸まで。足裏板までの距離は含めない。開脚角はこれを使う。
LEG_LENGTH_HIP_TO_ANKLE_M = _module.LEG_LENGTH_HIP_TO_ANKLE_M
# 全関節 0 のとき、カゴ底（原点）から足裏まで。出現位置はこれより 1 cm 上。
SOLE_BELOW_ORIGIN_M = _module.SOLE_BELOW_ORIGIN_M
# 左右の股ロール軸の間隔。足リンクの左右差は、関節 0 でこれと同じ。
HIP_SEPARATION_M = _module.HIP_SEPARATION_M
# 足裏板の左右幅。中心間隔の目標は、この幅に内側の隙間を足したもの。
PLATE_WIDTH_Y_M = _module.PLATE_WIDTH_Y_M
