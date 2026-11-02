"""等身大ヒューマノイドを STEP にする。

既存のカゴ脚（export_step.py）とは別の機体である。寸法は humanoid/params.py。

実行（リポジトリルート）:
    python cad/export_humanoid.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# このファイルを直接起動しても cad/ をパッケージとして読めるようにする。
_CAD_DIR = Path(__file__).resolve().parent
if str(_CAD_DIR) not in sys.path:
    sys.path.insert(0, str(_CAD_DIR))

from check_step import assert_aabb_matches
from export_step import write_step
from humanoid.body import standing_parts
from humanoid.params import STATURE_M
from humanoid.solids import aabb_of, make_parts

# 生成物。手で直さない。cad/out/ は gitignore 済み。
OUT_DIR = _CAD_DIR / "out"


def _solid_aabb(solid) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """build123d の境界。モデルと同じメートル。"""
    box = solid.bounding_box()
    return (box.min.X, box.min.Y, box.min.Z), (box.max.X, box.max.Y, box.max.Z)


def _assert_kernel_aabb(solids: list, expected) -> None:
    """書き出す前に、build123d の境界が部品リストと一致するか見る。"""
    from build123d import Compound

    got = _solid_aabb(Compound(children=solids))
    for got_corner, expect_corner in zip(got, expected):
        for got_value, expect_value in zip(got_corner, expect_corner):
            # 円柱の境界は解析値と 0.001 mm 以内。
            if abs(got_value - expect_value) > 1.0e-6:
                raise RuntimeError(
                    f"build123d の外形が部品リストと違います: {got} と {expected}"
                )


def main() -> int:
    specs = standing_parts()
    expected = aabb_of(specs)
    solids = make_parts(specs)
    _assert_kernel_aabb(solids, expected)
    path = OUT_DIR / "yuuki_humanoid.step"
    write_step(solids, path)
    unit = assert_aabb_matches(path, expected)

    low, high = expected
    height = high[2] - low[2]
    if abs(low[2]) > 1.0e-9:
        raise RuntimeError(f"足裏が床（z=0）にありません: {low[2]}")
    if abs(high[2] - STATURE_M) > 1.0e-9:
        raise RuntimeError(f"頭頂が {STATURE_M:.3f} m ではありません: {high[2]}")
    span = tuple((high[axis] - low[axis]) * 1000.0 for axis in range(3))
    print(f"ok  {path.name}  parts={len(specs)}  step_unit_read_as={unit}")
    print(
        f"  外形: 前後 {span[0]:.1f} mm, 左右 {span[1]:.1f} mm, 身長 {span[2]:.1f} mm"
    )
    print(f"  足裏 z {low[2] * 1000:.1f} mm, 頭頂 z {high[2] * 1000:.1f} mm")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
