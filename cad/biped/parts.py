"""URDF の直方体を、build123d の立体にする。

ここでの形はシミュレーション用の箱と同じである。サーボの穴、ホーン、
金具の曲げはまだ無い。寸法を STEP で往復できるかのテストが先である。

build123d の中身は Open CASCADE である。このファイルは高い方の API だけを使う。
STEP を読み戻して寸法を確かめる処理は check_step.py が OCP を直接呼ぶ。
"""

from __future__ import annotations

from dataclasses import dataclass

# generate_urdf.BoxPart と同じ並び。size はフルサイズ、center は箱の中心。
# 単位はメートル。yaml と URDF に合わせる。


@dataclass(frozen=True)
class PlacedBox:
    """世界座標に置いた直方体。原点は股ロール軸の高さ、左右の中央。"""

    name: str
    size_m: tuple[float, float, float]
    center_m: tuple[float, float, float]
    color: tuple[float, float, float, float]


def _require_positive(size_m: tuple[float, float, float], name: str) -> None:
    if any(value <= 0.0 for value in size_m):
        raise ValueError(f"{name} の寸法が正ではありません: {size_m}")


def make_box(part: PlacedBox):
    """中心が center_m の直方体。軸は世界の x y z と平行（直立、全関節 0）。"""
    from build123d import Box, Color, Pos

    _require_positive(part.size_m, part.name)
    # Box は原点中心。Pos で中心へ平行移動する。回転は無い。
    solid = Pos(part.center_m[0], part.center_m[1], part.center_m[2]) * Box(
        part.size_m[0], part.size_m[1], part.size_m[2]
    )
    # STEP に部品名を残す。読み戻し側は名前ではなく外形で確かめる。
    solid.label = part.name
    red, green, blue, alpha = part.color
    solid.color = Color(red, green, blue, alpha)
    return solid


def make_boxes(parts: list[PlacedBox]) -> list:
    """部品ごとの立体。1つの塊にはしない。名前を STEP に残すため。"""
    if not parts:
        raise ValueError("立体にする箱がありません")
    return [make_box(part) for part in parts]


def aabb_of(parts: list[PlacedBox]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """箱の並びから、世界座標の軸平行境界を計算する。カーネルは使わない。"""
    if not parts:
        raise ValueError("境界を取る箱がありません")
    lows = []
    highs = []
    for part in parts:
        half = tuple(size / 2.0 for size in part.size_m)
        lows.append(tuple(center - half[axis] for axis, center in enumerate(part.center_m)))
        highs.append(tuple(center + half[axis] for axis, center in enumerate(part.center_m)))
    low = tuple(min(item[axis] for item in lows) for axis in range(3))
    high = tuple(max(item[axis] for item in highs) for axis in range(3))
    return low, high
