"""書き出した STEP を Open CASCADE で読み、外形が元の箱と一致するか見る。

build123d の export は通っても、単位の取り違えで 1000 倍になることがある。
ここでは OCP の STEP リーダと境界箱で、数値を直接比べる。
"""

from __future__ import annotations

from pathlib import Path

from biped.parts import PlacedBox

# 箱は平面なので、読み戻しの誤差はこれよりずっと小さい想定。0.05 mm まで許す。
TOLERANCE_MM = 0.05


def read_shape(path: Path):
    """STEP の全形状を1つにまとめて返す。単位はリーダ任せ（多くは mm）。"""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP を読めません: {path}（status={status}）")
    # TransferRoots は移した根の個数を返す。0 なら形状が無い。
    if reader.TransferRoots() < 1:
        raise RuntimeError(f"STEP に移せる形状がありません: {path}")
    return reader.OneShape()


def shape_aabb(shape) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """形状の軸平行境界。座標の単位は STEP リーダが返したまま。"""
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box

    box = Bnd_Box()
    # 静的メソッド。曲面のたわみは使わず、頂点を含む境界にする。
    # OCP 8 の Bnd_Box.Get は Limits を返し、Python から解けない。成分で取る。
    BRepBndLib.Add_s(shape, box)
    return (
        (box.GetXMin(), box.GetYMin(), box.GetZMin()),
        (box.GetXMax(), box.GetYMax(), box.GetZMax()),
    )


def _scale_error(
    got: tuple[tuple[float, float, float], tuple[float, float, float]],
    expected_m: tuple[tuple[float, float, float], tuple[float, float, float]],
    millimeters_per_model_unit: float,
) -> float:
    """期待値をリーダの単位へ換算したときの、6成分の最大誤差。"""
    expected = expected_m[0] + expected_m[1]
    actual = got[0] + got[1]
    worst = 0.0
    for got_value, meter_value in zip(actual, expected):
        worst = max(worst, abs(got_value - meter_value * millimeters_per_model_unit))
    return worst


def assert_aabb_matches(
    path: Path,
    expected_m: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> str:
    """STEP の境界が、メートルで与えた期待値と一致することを確かめる。

    リーダが mm を返す場合と、ファイルの数値をそのまま返す場合の両方を見る。
    一致した方の単位名を返す。どちらでもなければ、読んだ境界を添えて止める。
    """
    got = shape_aabb(read_shape(path))
    # Open CASCADE の STEP リーダは、通常メートルを mm に直して返す。
    candidates = ((1000.0, "mm"), (1.0, "m"))
    best_name = ""
    best_error = float("inf")
    for scale, name in candidates:
        error = _scale_error(got, expected_m, scale)
        limit = TOLERANCE_MM if scale == 1000.0 else TOLERANCE_MM / 1000.0
        if error <= limit:
            return name
        if error < best_error:
            best_error = error
            best_name = name
    raise RuntimeError(
        f"{path.name} の外形が期待と違います。"
        f" 読んだ境界 {got[0]} → {got[1]}、"
        f" 期待（m） {expected_m[0]} → {expected_m[1]}。"
        f" 最も近い解釈は {best_name} で誤差 {best_error:.6g}。"
    )


def expected_from_parts(
    parts: list[PlacedBox],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """部品リストと同じ境界を、カーネルを通さずに返す。"""
    from biped.parts import aabb_of

    return aabb_of(parts)
