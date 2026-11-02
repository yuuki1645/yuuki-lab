"""部品仕様を build123d の立体にする。

円柱は、作った直後は Z 軸が軸である。ピッチ関節は X 軸まわりに 90 度回して、
軸を Y に向ける。境界箱はこの向きから計算し、カーネルの外形と突き合わせる。
"""

from __future__ import annotations

from humanoid.body import PartSpec


def part_aabb(
    spec: PartSpec,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """1部品の軸平行境界。回転後の向きで計算する。"""
    center = spec.center_m
    if spec.kind == "box":
        if spec.size_m is None:
            raise ValueError(f"{spec.name} に寸法がありません")
        half = tuple(size / 2.0 for size in spec.size_m)
    elif spec.kind == "zcyl":
        half = _cylinder_half(spec, (1, 1, 0))
    elif spec.kind == "ycyl":
        # 軸は Y。半径は X と Z に出る。
        half = _cylinder_half(spec, (1, 0, 1))
    elif spec.kind == "sphere":
        if spec.radius_m is None:
            raise ValueError(f"{spec.name} に半径がありません")
        half = (spec.radius_m, spec.radius_m, spec.radius_m)
    else:
        raise ValueError(f"未知の部品種別です: {spec.kind}")
    low = tuple(center[axis] - half[axis] for axis in range(3))
    high = tuple(center[axis] + half[axis] for axis in range(3))
    return low, high


def _cylinder_half(spec: PartSpec, radius_on: tuple[int, int, int]) -> tuple[float, float, float]:
    """radius_on が 1 の軸は半径、0 の軸は長さの半分。"""
    if spec.radius_m is None or spec.length_m is None:
        raise ValueError(f"{spec.name} に円柱の半径または長さがありません")
    half_length = spec.length_m / 2.0
    return tuple(
        spec.radius_m if radius_on[axis] else half_length for axis in range(3)
    )


def aabb_of(
    specs: list[PartSpec],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """全部品を包む境界。"""
    if not specs:
        raise ValueError("部品がありません")
    boxes = [part_aabb(spec) for spec in specs]
    low = tuple(min(box[0][axis] for box in boxes) for axis in range(3))
    high = tuple(max(box[1][axis] for box in boxes) for axis in range(3))
    return low, high


def make_part(spec: PartSpec):
    """1部品を、中心が世界座標に来る立体にする。"""
    from build123d import Box, Color, Cylinder, Pos, Rot, Sphere

    if spec.kind == "box":
        if spec.size_m is None:
            raise ValueError(f"{spec.name} に寸法がありません")
        shape = Box(spec.size_m[0], spec.size_m[1], spec.size_m[2])
    elif spec.kind == "zcyl":
        shape = Cylinder(spec.radius_m, spec.length_m)
    elif spec.kind == "ycyl":
        # 右手系で X 軸に +90 度。円柱の軸（もとの Z）が Y 軸に倒れる。
        shape = Rot(X=90) * Cylinder(spec.radius_m, spec.length_m)
    elif spec.kind == "sphere":
        shape = Sphere(spec.radius_m)
    else:
        raise ValueError(f"未知の部品種別です: {spec.kind}")
    solid = Pos(spec.center_m[0], spec.center_m[1], spec.center_m[2]) * shape
    solid.label = spec.name
    red, green, blue, alpha = spec.color
    solid.color = Color(red, green, blue, alpha)
    return solid


def make_parts(specs: list[PartSpec]) -> list:
    """部品ごとの立体。名前を STEP に残すため、1つにはまとめない。"""
    return [make_part(spec) for spec in specs]
