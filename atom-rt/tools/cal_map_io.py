"""
AS5600 unwrap → サーボ指令の校正マップを JSON で読み書きする。

servo_monitor / rt_monitor の共通形式。
"""

from __future__ import annotations

import json
from pathlib import Path


FORMAT = "as5600-servo-map-v1"


def save_map(path: str | Path, channel: int, points: list[tuple[float, float]]) -> None:
    """points は (as5600_unwrap, servo_cmd) の列。"""
    data = {
        "format": FORMAT,
        "channel": int(channel),
        "count": len(points),
        "points": [{"as5600": float(x), "servo": float(y)} for x, y in points],
    }
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_map(path: str | Path) -> tuple[int, list[tuple[float, float]]]:
    """@return (channel, points)"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("format") == FORMAT:
        ch = int(data.get("channel", 0))
        pts = []
        for p in data.get("points", []):
            if isinstance(p, dict):
                pts.append((float(p["as5600"]), float(p["servo"])))
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                pts.append((float(p[0]), float(p[1])))
        return ch, pts
    raise ValueError("未対応のマップファイルです")
