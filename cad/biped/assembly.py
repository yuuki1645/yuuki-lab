"""全関節 0 のとき、URDF と同じ位置に箱を置く。

関節の rpy はいま全部 0 なので、子の原点は親の原点に joint.origin を足すだけである。
回転が入ったら、この平行移動だけでは足りない。そのときはここで止める。

IMU と足裏中心の球は、質量がほぼゼロの参照点である。金物ではないので立体にしない。
足裏の高さは足板の下面で見る。
"""

from __future__ import annotations

from biped.params import generator, load_model
from biped.parts import PlacedBox

# カタログ寸法のままのサーボ。股や足首のように下端を削った箱とは別。
CATALOG_SERVO_NAME = "servo_rds51150"


def _link_origins(links, joints) -> dict[str, tuple[float, float, float]]:
    """各リンク原点の世界座標。根（カゴ）は (0, 0, 0)。"""
    if not links:
        raise ValueError("リンクがありません")
    origin: dict[str, tuple[float, float, float]] = {links[0].name: (0.0, 0.0, 0.0)}
    pending = list(joints)
    guard = 0
    while pending:
        guard += 1
        if guard > len(joints) + 2:
            names = ", ".join(joint.child for joint in pending)
            raise RuntimeError(f"リンクの位置を決められません: {names}")
        still = []
        for joint in pending:
            # 生成スクリプトは rpy を書いていない。回転が来たら位置計算を直す。
            if joint.rpy != (0.0, 0.0, 0.0):
                raise RuntimeError(
                    f"{joint.name} に回転があります。平行移動だけでは置けません: {joint.rpy}"
                )
            if joint.parent not in origin:
                still.append(joint)
                continue
            parent = origin[joint.parent]
            origin[joint.child] = (
                parent[0] + joint.origin[0],
                parent[1] + joint.origin[1],
                parent[2] + joint.origin[2],
            )
        pending = still
    return origin


def _is_box(part) -> bool:
    """球の参照点を落とす。BoxPart かどうかは属性で見る。"""
    return hasattr(part, "size") and hasattr(part, "collision")


def placed_boxes(links, joints, link_names: set[str] | None = None) -> list[PlacedBox]:
    """選んだリンクの箱を世界座標にする。link_names が None なら全部。"""
    origins = _link_origins(links, joints)
    placed: list[PlacedBox] = []
    for link in links:
        if link_names is not None and link.name not in link_names:
            continue
        base = origins[link.name]
        box_index = 0
        for part in link.parts:
            if not _is_box(part):
                continue
            # 同じリンクに板が2枚あるので、名前に通し番号を付ける。
            name = f"{link.name}_{part.name}_{box_index}"
            box_index += 1
            placed.append(
                PlacedBox(
                    name=name,
                    size_m=tuple(part.size),
                    center_m=(
                        base[0] + part.origin[0],
                        base[1] + part.origin[1],
                        base[2] + part.origin[2],
                    ),
                    color=tuple(part.color),
                )
            )
    if not placed:
        raise RuntimeError("置く箱がありません")
    return placed


def catalog_servo(params: dict) -> PlacedBox:
    """ピッチ向きのサーボ1個。軸は原点、上端は軸の axis_inset 上。

    寸法は yaml の servo.size_m。股ロールのように 90 度回した箱ではない。
    この1個が、STEP 往復の最初の合格条件になる。
    """
    # 下端を削らず、ロール用の 90 度回転もしない。yaml の並びのまま。
    part = generator().servo_box(params)
    return PlacedBox(
        name=CATALOG_SERVO_NAME,
        size_m=tuple(part.size),
        center_m=tuple(part.origin),
        color=tuple(part.color),
    )


def leg_link_names(side: str) -> set[str]:
    """片脚のリンク名。カゴと IMU は含めない。"""
    if side not in ("left", "right"):
        raise ValueError("side は left か right です")
    return {
        f"{side}_hip",
        f"{side}_thigh",
        f"{side}_shin",
        f"{side}_ankle",
        f"{side}_foot",
    }


def build_standing(path=None) -> tuple[dict, list[PlacedBox]]:
    """yaml から、直立の全箱を作る。"""
    params, links, joints = load_model(path)
    return params, placed_boxes(links, joints)


def build_leg(side: str = "left", path=None) -> tuple[dict, list[PlacedBox]]:
    """片脚だけ。位置は全身と同じ世界座標のまま（股の y は ±hip_y）。"""
    params, links, joints = load_model(path)
    return params, placed_boxes(links, joints, leg_link_names(side))
