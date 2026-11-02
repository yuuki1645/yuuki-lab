"""直立の箱モデルを STEP にする。

最初にサーボ1個を書き、Open CASCADE で読み戻して 30×48×65 mm を確かめる。
それが通ってから、左脚と、カゴを含む両脚を書く。

実行（リポジトリルート）:
    python cad/export_step.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# このファイルを直接起動しても cad/ をパッケージとして読めるようにする。
_CAD_DIR = Path(__file__).resolve().parent
if str(_CAD_DIR) not in sys.path:
    sys.path.insert(0, str(_CAD_DIR))

from biped.assembly import build_leg, build_standing, catalog_servo
from biped.params import generator, load_params
from biped.parts import aabb_of, make_boxes
from check_step import assert_aabb_matches

# 生成物。手で直さない。
OUT_DIR = _CAD_DIR / "out"


def _solid_aabb(solid) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """build123d の境界。モデルと同じメートル。"""
    box = solid.bounding_box()
    low = (box.min.X, box.min.Y, box.min.Z)
    high = (box.max.X, box.max.Y, box.max.Z)
    return low, high


def _assert_kernel_aabb(solids: list, expected) -> None:
    """書き出す前に、build123d の境界が部品リストと一致するか見る。"""
    from build123d import Compound

    got = _solid_aabb(Compound(children=solids))
    for got_corner, expect_corner in zip(got, expected):
        for got_value, expect_value in zip(got_corner, expect_corner):
            if abs(got_value - expect_value) > 1.0e-9:
                raise RuntimeError(
                    f"build123d の外形が部品リストと違います: {got} と {expected}"
                )


def write_step(solids: list, path: Path) -> None:
    """立体のリストを1つの STEP にする。数値はメートルのまま書く。"""
    from build123d import Compound, Unit, export_step

    path.parent.mkdir(parents=True, exist_ok=True)
    # Python 側の数値はメートル。Unit.M はその宣言で、STEP の中身は
    # ミリメートルになる（サーボ半幅 0.015 m はファイル上の 15）。
    # Unit.MM のままだと、0.030 が 0.030 mm として書かれる。
    assembly = Compound(children=solids, label=path.stem)
    wrote = export_step(assembly, path, unit=Unit.M)
    if wrote is False:
        raise RuntimeError(f"STEP を書けませんでした: {path}")


def export_and_check(parts, path: Path) -> str:
    """立体化、カーネル内の境界確認、STEP 書き出し、OCP での読み戻し。"""
    solids = make_boxes(parts)
    expected = aabb_of(parts)
    _assert_kernel_aabb(solids, expected)
    write_step(solids, path)
    unit = assert_aabb_matches(path, expected)
    print(f"ok  {path.name}  parts={len(parts)}  step_unit_read_as={unit}")
    return unit


def _print_span(title: str, parts) -> None:
    """外形の幅をミリメートルで1行出す。確認用。"""
    low, high = aabb_of(parts)
    span = tuple((high[axis] - low[axis]) * 1000.0 for axis in range(3))
    print(
        f"  {title}: x {span[0]:.1f} mm, y {span[1]:.1f} mm, z {span[2]:.1f} mm"
        f"  （z {low[2] * 1000:.1f} … {high[2] * 1000:.1f}）"
    )


def main() -> int:
    params = load_params()
    servo = [catalog_servo(params)]
    # カタログ寸法。下端を削る股・足首サーボとは違う。
    size_mm = tuple(value * 1000.0 for value in servo[0].size_m)
    print(
        "サーボ（ピッチ向き、軸は原点）: "
        f"{size_mm[0]:.1f} × {size_mm[1]:.1f} × {size_mm[2]:.1f} mm"
    )
    export_and_check(servo, OUT_DIR / "servo_rds51150.step")

    _, left = build_leg("left")
    _print_span("左脚", left)
    export_and_check(left, OUT_DIR / "left_leg.step")

    _, standing = build_standing()
    _print_span("両脚とカゴ", standing)
    export_and_check(standing, OUT_DIR / "yuuki_biped.step")

    # 直立の目安。robot_description の 0.640 m / 0.802 m とずれたら、箱の置き方が URDF と違う。
    sole_drop = generator().standing_sole_drop(params)
    basket_top = params["axis_inset"] + params["clearance"] + params["basket_size"][2]
    low, high = aabb_of(standing)
    height = high[2] - low[2]
    if abs(low[2] - (-sole_drop)) > 1.0e-9:
        raise RuntimeError(f"足裏が原点から {sole_drop:.3f} m 下にありません: {low[2]}")
    if abs(high[2] - basket_top) > 1.0e-9:
        raise RuntimeError(f"カゴ天面が {basket_top:.3f} m ではありません: {high[2]}")
    print(f"  足裏からカゴ天面まで {height * 1000:.1f} mm")
    print(f"wrote {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
