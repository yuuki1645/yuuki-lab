"""yaml から、URDF・学習・再生が同じ寸法を読む。

関節の式は generate_urdf.py の resolve_params と揃えてある。
yaml を変えたら generate_urdf.py を実行し、この値も次の起動から変わる。
"""

from __future__ import annotations

from pathlib import Path

import yaml

_YAML = Path(__file__).resolve().parent / "yuuki_biped.yaml"


def _load() -> dict:
    """派生寸法。カゴ底（原点）から足裏までと、開脚に使う脚の長さ。"""
    with _YAML.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    servo_z = float(raw["servo"]["size_m"][2])
    axis_inset = float(raw["servo"]["axis_inset_m"])
    plate_z = float(raw["plate"]["size_m"][2])
    stacked = raw["placement"]["stacked_servo_distance_m"]
    segment = raw["placement"]["segment_axis_distance_m"]
    # null は生成スクリプトと同じ式。軸の位置はここで変えない。
    stacked_m = float(servo_z if stacked is None else stacked)
    segment_m = float((2.0 * axis_inset + plate_z) if segment is None else segment)
    sole_m = float(raw["foot"]["ankle_to_sole_m"])
    return {
        # 股ピッチ、膝、足首ピッチ、足首ロール。足裏までの 58 mm は含めない。
        "LEG_LENGTH_HIP_TO_ANKLE_M": stacked_m + segment_m + segment_m + stacked_m,
        "SOLE_BELOW_ORIGIN_M": 2.0 * stacked_m + 2.0 * segment_m + sole_m,
        "HIP_SEPARATION_M": 2.0 * float(raw["placement"]["hip_y_m"]),
        "PLATE_WIDTH_Y_M": float(raw["foot"]["size_m"][1]),
        "CLEARANCE_M": float(raw["placement"]["clearance_m"]),
    }


_VALUES = _load()
LEG_LENGTH_HIP_TO_ANKLE_M = _VALUES["LEG_LENGTH_HIP_TO_ANKLE_M"]
SOLE_BELOW_ORIGIN_M = _VALUES["SOLE_BELOW_ORIGIN_M"]
HIP_SEPARATION_M = _VALUES["HIP_SEPARATION_M"]
PLATE_WIDTH_Y_M = _VALUES["PLATE_WIDTH_Y_M"]
CLEARANCE_M = _VALUES["CLEARANCE_M"]
