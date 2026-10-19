#!/usr/bin/env python3
"""yuuki_biped.yaml から脚部ロボットの URDF を生成する。

手で直すのは yaml だけ。このスクリプトは慣性テンソルを箱の寸法と質量から
計算し、関節の原点をパラメータ通りに並べる。URDF の box size はフルサイズ
（MuJoCo の half-size ではない）。

実行例（プロジェクトルート）:
    python robot_description/generate_urdf.py
"""

from __future__ import annotations

import argparse
import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# このファイルと同じディレクトリが、設定と生成物の置き場。
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "yuuki_biped.yaml"
DEFAULT_OUTPUT = SCRIPT_DIR / "yuuki_biped.urdf"

# 見た目の色。寸法には影響しない。RGBA。
COLOR_BASKET = (0.93, 0.93, 0.90, 1.0)
COLOR_SERVO = (0.45, 0.12, 0.16, 1.0)
COLOR_PLATE = (0.78, 0.80, 0.82, 1.0)
# ダンボールの色。中のセルは別の箱にしない。
COLOR_BATTERY = (0.72, 0.58, 0.40, 1.0)
COLOR_FOOT = (0.82, 0.83, 0.84, 1.0)
COLOR_IMU = (0.95, 0.85, 0.15, 1.0)
COLOR_SOLE = (0.85, 0.25, 0.20, 1.0)

# ログに出す「図面に無く、仮置きしている」項目。yaml を実測値へ変えたらここも更新する。
ASSUMED_KEYS = (
    "basket.mass_kg",
    "plate.center_y_m",
    "foot.center_x_m",
    "foot.ankle_to_sole_m",
    "placement.hip_x_m",
    "placement.hip_y_m",
    "placement.stacked_servo_distance_m（null のときサーボ長）",
    "placement.segment_axis_distance_m（null のとき 13mm+板長+13mm）",
    "placement.clearance_m（未計測の隙間。箱が食い込まない側）",
    "imu.xyz_m",
    "actuator.velocity_limit_rad_s",
    "joints_deg の全部",
    "right_roll_axis_sign",
)


@dataclass
class BoxPart:
    """リンク座標における直方体。origin は箱の中心。size はフルサイズ。"""

    name: str
    size: tuple[float, float, float]
    origin: tuple[float, float, float]
    mass: float
    color: tuple[float, float, float, float]
    collision: bool = True


@dataclass
class SpherePart:
    """質量をほぼ持たない参照用の球（IMU、足裏中心）。"""

    name: str
    radius: float
    origin: tuple[float, float, float]
    mass: float
    color: tuple[float, float, float, float]
    collision: bool = False


@dataclass
class Inertial:
    """URDF の <inertial>。原点は重心。慣性は重心まわり。"""

    origin: tuple[float, float, float]
    mass: float
    ixx: float
    ixy: float
    ixz: float
    iyy: float
    iyz: float
    izz: float


@dataclass
class Link:
    name: str
    parts: list[BoxPart | SpherePart] = field(default_factory=list)
    inertial: Inertial | None = None


@dataclass
class Joint:
    name: str
    joint_type: str
    parent: str
    child: str
    origin: tuple[float, float, float]
    rpy: tuple[float, float, float] = (0.0, 0.0, 0.0)
    axis: tuple[float, float, float] | None = None
    lower: float | None = None
    upper: float | None = None
    effort: float | None = None
    velocity: float | None = None
    damping: float = 0.0
    friction: float = 0.0
    comment: str = ""


def fmt(value: float) -> str:
    """URDF に書く数値。末尾の 0 を落とし、-0 は 0 にする。"""
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        return "0"
    return text


def vec3(values: tuple[float, float, float]) -> str:
    return " ".join(fmt(v) for v in values)


def rgba(color: tuple[float, float, float, float]) -> str:
    return " ".join(fmt(c) for c in color)


def require_vec3(data: dict, key: str, label: str) -> tuple[float, float, float]:
    raw = data[key]
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise ValueError(f"{label}.{key} は長さ3の配列にしてください: {raw!r}")
    return (float(raw[0]), float(raw[1]), float(raw[2]))


def box_inertia_about_center(
    mass: float, size: tuple[float, float, float]
) -> tuple[float, float, float]:
    """軸が箱の辺に平行なときの、中心まわりの主慣性モーメント。

    Ixx = m/12 * (y^2 + z^2) など。製品慣性（ixy 等）は 0。
    """
    x, y, z = size
    return (
        mass * (y * y + z * z) / 12.0,
        mass * (x * x + z * z) / 12.0,
        mass * (x * x + y * y) / 12.0,
    )


def sphere_inertia(mass: float, radius: float) -> float:
    """一様球の中心まわり慣性。3軸とも同じ。"""
    return 0.4 * mass * radius * radius


def combine_inertial(parts: list[BoxPart | SpherePart]) -> Inertial:
    """複数部品の質量・重心・慣性を、平行軸の定理で1つの inertial にまとめる。"""
    total = sum(part.mass for part in parts)
    if total <= 0.0:
        raise ValueError("リンク質量が 0 以下です")

    com_x = sum(part.mass * part.origin[0] for part in parts) / total
    com_y = sum(part.mass * part.origin[1] for part in parts) / total
    com_z = sum(part.mass * part.origin[2] for part in parts) / total

    ixx = iyy = izz = 0.0
    ixy = ixz = iyz = 0.0
    for part in parts:
        if isinstance(part, BoxPart):
            lx, ly, lz = box_inertia_about_center(part.mass, part.size)
        else:
            lx = ly = lz = sphere_inertia(part.mass, part.radius)
        # 部品中心から、リンク重心までのずれ。
        dx = part.origin[0] - com_x
        dy = part.origin[1] - com_y
        dz = part.origin[2] - com_z
        ixx += lx + part.mass * (dy * dy + dz * dz)
        iyy += ly + part.mass * (dx * dx + dz * dz)
        izz += lz + part.mass * (dx * dx + dy * dy)
        ixy += -part.mass * dx * dy
        ixz += -part.mass * dx * dz
        iyz += -part.mass * dy * dz

    return Inertial((com_x, com_y, com_z), total, ixx, ixy, ixz, iyy, iyz, izz)


def resolve_params(raw: dict) -> dict:
    """null の距離を寸法から埋め、角度をラジアンにした辞書を返す。"""
    basket = raw["basket"]
    servo = raw["servo"]
    plate = raw["plate"]
    battery = raw["battery"]
    foot = raw["foot"]
    placement = raw["placement"]
    imu = raw["imu"]
    actuator = raw["actuator"]

    basket_size = require_vec3(basket, "size_m", "basket")
    servo_size = require_vec3(servo, "size_m", "servo")
    plate_size = require_vec3(plate, "size_m", "plate")
    # セル寸法は記録。衝突箱は側板の空きから後で作る。
    battery_cell = require_vec3(battery, "cell_size_m", "battery")
    foot_size = require_vec3(foot, "size_m", "foot")
    imu_xyz = require_vec3(imu, "xyz_m", "imu")

    axis_inset = float(servo["axis_inset_m"])
    stacked = placement["stacked_servo_distance_m"]
    segment = placement["segment_axis_distance_m"]
    # null は「サーボをそのまま1段積んだ距離」。
    clearance = float(placement["clearance_m"])
    stacked_distance = float(servo_size[2] if stacked is None else stacked)
    # null は「両端の軸が板から 13 mm ずつ外側」。
    segment_distance = float(
        (2.0 * axis_inset + plate_size[2]) if segment is None else segment
    )

    sign = float(raw["right_roll_axis_sign"])
    if sign not in (1.0, -1.0):
        raise ValueError("right_roll_axis_sign は 1 か -1 です")

    joints_deg = raw["joints_deg"]
    joints_rad: dict[str, tuple[float, float]] = {}
    for name, pair in joints_deg.items():
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"joints_deg.{name} は [下限, 上限] です")
        lower = math.radians(float(pair[0]))
        upper = math.radians(float(pair[1]))
        if lower >= upper:
            raise ValueError(f"joints_deg.{name} は下限 < 上限にしてください")
        joints_rad[name] = (lower, upper)

    params = {
        "robot_name": str(raw.get("robot_name", "yuuki_biped")),
        "basket_size": basket_size,
        "basket_mass": float(basket["mass_kg"]),
        "servo_size": servo_size,
        "servo_mass": float(servo["mass_kg"]),
        "axis_inset": axis_inset,
        "plate_size": plate_size,
        "plate_mass": float(plate["mass_kg"]),
        "plate_center_y": float(plate["center_y_m"]),
        "battery_cell": battery_cell,
        "battery_mass": float(battery["mass_kg"]),
        "clearance": clearance,
        "battery_on_shin": bool(battery["on_shin"]),
        "foot_size": foot_size,
        "foot_mass": float(foot["mass_kg"]),
        "foot_center_x": float(foot["center_x_m"]),
        "ankle_to_sole": float(foot["ankle_to_sole_m"]),
        "hip_x": float(placement["hip_x_m"]),
        "hip_y": float(placement["hip_y_m"]),
        "stacked_distance": stacked_distance,
        "segment_distance": segment_distance,
        "imu_xyz": imu_xyz,
        "imu_mass": float(imu["mass_kg"]),
        "effort": float(actuator["effort_nm"]),
        "velocity": float(actuator["velocity_limit_rad_s"]),
        "damping": float(actuator["damping"]),
        "friction": float(actuator["friction"]),
        "joints_rad": joints_rad,
        "right_roll_axis_sign": sign,
    }
    _validate(params)
    return params


def _validate(params: dict) -> None:
    """負の寸法や、板より短い軸間など、生成すると壊れる値を止める。"""
    positive_keys = (
        "basket_mass",
        "servo_mass",
        "plate_mass",
        "battery_mass",
        "foot_mass",
        "hip_y",
        "stacked_distance",
        "segment_distance",
        "ankle_to_sole",
        "clearance",
        "effort",
        "velocity",
        "axis_inset",
        "plate_center_y",
    )
    for key in positive_keys:
        if params[key] <= 0.0:
            raise ValueError(f"{key} は正の数にしてください（今は {params[key]}）")
    for label, size in (
        ("basket", params["basket_size"]),
        ("servo", params["servo_size"]),
        ("plate", params["plate_size"]),
        ("battery_cell", params["battery_cell"]),
        ("foot", params["foot_size"]),
    ):
        if any(v <= 0.0 for v in size):
            raise ValueError(f"{label} の size はすべて正にしてください: {size}")
    if params["axis_inset"] >= params["servo_size"][2]:
        raise ValueError("servo.axis_inset_m はサーボの脚方向長さより短くしてください")
    # 板が軸間に収まらないと、次の関節が板の途中に来る。
    if params["segment_distance"] <= params["plate_size"][2]:
        raise ValueError(
            "segment_axis_distance は板の長さより長くしてください"
            "（軸が板の両端の外側にある、という仮定）"
        )
    if params["clearance"] >= params["servo_size"][2] / 2.0:
        raise ValueError("clearance_m がサーボの半分以上です。箱が消えません")
    # サーボ下端、板の厚さ、隙間。これより足裏が近いと、足サーボが板を貫く。
    servo_below = params["servo_size"][2] - params["axis_inset"]
    min_sole = servo_below + params["foot_size"][2] + params["clearance"]
    if params["ankle_to_sole"] + 1.0e-9 < min_sole:
        raise ValueError(
            "foot.ankle_to_sole_m が短く、足サーボが足裏板に入ります。"
            f" 必要 {min_sole:.4f} m、今 {params['ankle_to_sole']:.4f} m。"
        )
    servo_half_y = params["servo_size"][1] / 2.0
    plate_half_y = params["plate_size"][1] / 2.0
    min_plate_y = servo_half_y + params["clearance"] + plate_half_y
    if params["plate_center_y"] + 1.0e-9 < min_plate_y:
        raise ValueError(
            "plate.center_y_m が小さく、側板がサーボに入ります。"
            f" 必要 {min_plate_y:.4f} m、今 {params['plate_center_y']:.4f} m。"
        )
    housing = _battery_housing(params)
    if min(housing[0]) <= 0.0:
        raise ValueError(f"電池のダンボールが空きに入りません: {housing[0]}")


def servo_box(params: dict, shorten_bottom: float = 0.0, yaw_quarter_turn: bool = False) -> BoxPart:
    """サーボ箱。上端は軸の axis_inset 上。下端だけ短くして、次の部品と隙間を空ける。

    質量はカタログのサーボのまま。削るのはホーンと金具の分で、金属が消えたわけではない。
    ピッチ軸（左右が軸）の箱は、前後 30 mm、左右 48 mm。
    ロール軸（前後が軸）の箱は yaw_quarter_turn で脚まわりに 90 度回し、前後 48 mm、左右 30 mm。
    実機は隣り合うサーボのケースが互い違いで、ホーンの向きが軸と揃っている。
    中心は軸上なので、回しても関節の位置は動かない。
    """
    length = params["servo_size"][2] - shorten_bottom
    # 上端を固定し、中心を下へずらさないようにする（下を削ると中心は上へ寄る）。
    center_z = params["axis_inset"] - length / 2.0
    width_x, width_y = params["servo_size"][0], params["servo_size"][1]
    if yaw_quarter_turn:
        width_x, width_y = width_y, width_x
    size = (width_x, width_y, length)
    return BoxPart(
        "servo",
        size,
        (0.0, 0.0, center_z),
        params["servo_mass"],
        COLOR_SERVO,
    )


def _battery_housing(params: dict) -> tuple[tuple[float, float, float], float]:
    """ダンボールの寸法と、リンク原点からの中心 z。

    上は自分のサーボの下端、下は次のリンクのサーボ上端。左右は側板の内側。
    それぞれ clearance だけ空ける。セルの 130 mm より長くても、空きの中ならこの箱にする。
    """
    clearance = params["clearance"]
    # このリンクのサーボはフル長。下端は軸から (胴体長 - inset) だけ下。
    servo_bottom = params["axis_inset"] - params["servo_size"][2]
    # 子リンクのサーボ上端。子の関節は segment だけ下にあり、上端は軸の inset 上。
    next_servo_top = -params["segment_distance"] + params["axis_inset"]
    top = servo_bottom - clearance
    bottom = next_servo_top + clearance
    length = top - bottom
    center_z = (top + bottom) / 2.0
    inner_y = 2.0 * (params["plate_center_y"] - params["plate_size"][1] / 2.0)
    size = (
        params["plate_size"][0] - 2.0 * clearance,
        inner_y - 2.0 * clearance,
        length,
    )
    return size, center_z


def segment_boxes(params: dict, include_battery: bool) -> list[BoxPart]:
    """ピッチ関節の子リンク。サーボ1個、側板2枚、あればダンボールの電池。

    板の上端は軸の axis_inset 下。長さは plate の z。軸間の式は変えない。
    サーボの側面と板のあいだ、サーボと電池のあいだには clearance を空ける。
    """
    parts = [servo_box(params)]
    # 上端は軸から inset の位置のまま。下端だけ短くし、次のサーボの上面と面で接しないようにする。
    # 仕様の板長 200 mm は軸間の式に残す。削るのは未計測の金具の隙間の分。
    plate_length = params["plate_size"][2] - params["clearance"]
    center_z = -(params["axis_inset"] + plate_length / 2.0)
    plate_size = (params["plate_size"][0], params["plate_size"][1], plate_length)
    lateral = params["plate_center_y"]
    for side in (1.0, -1.0):
        parts.append(
            BoxPart(
                "plate",
                plate_size,
                (0.0, side * lateral, center_z),
                params["plate_mass"],
                COLOR_PLATE,
            )
        )
    if include_battery:
        size, battery_z = _battery_housing(params)
        parts.append(
            BoxPart(
                "battery",
                size,
                (0.0, 0.0, battery_z),
                params["battery_mass"],
                COLOR_BATTERY,
            )
        )
    return parts


def foot_boxes(params: dict) -> list[BoxPart]:
    """足首ロールの子リンク。サーボと足板。足板の下面が z = -ankle_to_sole。"""
    thickness = params["foot_size"][2]
    sole_z = -params["ankle_to_sole"]
    center_z = sole_z + thickness / 2.0
    return [
        # 足首ロール。上の足首ピッチとはケースを 90 度ずらす。
        servo_box(params, yaw_quarter_turn=True),
        BoxPart(
            "foot_plate",
            params["foot_size"],
            (params["foot_center_x"], 0.0, center_z),
            params["foot_mass"],
            COLOR_FOOT,
        ),
    ]


def make_link(name: str, parts: list[BoxPart | SpherePart]) -> Link:
    return Link(name=name, parts=parts, inertial=combine_inertial(parts))


def revolute(
    name: str,
    parent: str,
    child: str,
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    limits: tuple[float, float],
    params: dict,
    comment: str,
) -> Joint:
    """limits は軸ベクトルの正方向に対する範囲。軸を反転したときは符号も反転する。"""
    lower, upper = limits
    if axis[0] < 0.0 or axis[1] < 0.0 or axis[2] < 0.0:
        # 軸を反転すると、同じ物理角度の範囲は [ -upper, -lower ] になる。
        lower, upper = -upper, -lower
    return Joint(
        name=name,
        joint_type="revolute",
        parent=parent,
        child=child,
        origin=origin,
        axis=axis,
        lower=lower,
        upper=upper,
        effort=params["effort"],
        velocity=params["velocity"],
        damping=params["damping"],
        friction=params["friction"],
        comment=comment,
    )


def build_model(params: dict) -> tuple[list[Link], list[Joint]]:
    """カゴを根にして、左右の脚を同じ関数で作る。"""
    links: list[Link] = []
    joints: list[Joint] = []

    basket_height = params["basket_size"][2]
    # 原点は股ロール軸の高さのまま。カゴの箱は、股サーボの上端より clearance だけ上から始める。
    # サーボ上端は軸の axis_inset 上なので、箱を底面に置くと股サーボがカゴへ 13 mm 入る。
    basket_bottom = params["axis_inset"] + params["clearance"]
    links.append(
        make_link(
            "basket",
            [
                BoxPart(
                    "basket",
                    params["basket_size"],
                    (0.0, 0.0, basket_bottom + basket_height / 2.0),
                    params["basket_mass"],
                    COLOR_BASKET,
                )
            ],
        )
    )
    links.append(
        make_link(
            "imu_link",
            [
                SpherePart(
                    "imu",
                    radius=0.012,
                    origin=(0.0, 0.0, 0.0),
                    mass=params["imu_mass"],
                    color=COLOR_IMU,
                )
            ],
        )
    )
    joints.append(
        Joint(
            name="imu_fixed",
            joint_type="fixed",
            parent="basket",
            child="imu_link",
            origin=params["imu_xyz"],
            comment="IMU 候補の参照フレーム。位置は未確認。質量はほぼゼロ。",
        )
    )

    for side, y_sign in (("left", 1.0), ("right", -1.0)):
        leg_links, leg_joints = build_leg(params, side, y_sign)
        links.extend(leg_links)
        joints.extend(leg_joints)
    return links, joints


def build_leg(
    params: dict, side: str, y_sign: float
) -> tuple[list[Link], list[Joint]]:
    """片脚。side は 'left' または 'right'。y_sign は左が +1。"""
    hip_name = f"{side}_hip"
    thigh_name = f"{side}_thigh"
    shin_name = f"{side}_shin"
    ankle_name = f"{side}_ankle"
    foot_name = f"{side}_foot"
    sole_name = f"{side}_sole"

    roll_sign = 1.0 if side == "left" else params["right_roll_axis_sign"]
    roll_axis = (roll_sign, 0.0, 0.0)
    pitch_axis = (0.0, 1.0, 0.0)

    links = [
        # 股ロール。下の股ピッチとはケースを 90 度ずらす。下端だけ隙間分短くする。軸は stacked のまま。
        make_link(
            hip_name,
            [servo_box(params, shorten_bottom=params["clearance"], yaw_quarter_turn=True)],
        ),
        make_link(thigh_name, segment_boxes(params, include_battery=True)),
        make_link(
            shin_name,
            segment_boxes(params, include_battery=params["battery_on_shin"]),
        ),
        # 下の足サーボと面が接しないよう、下端だけ隙間分短くする。
        make_link(ankle_name, [servo_box(params, shorten_bottom=params["clearance"])]),
        make_link(foot_name, foot_boxes(params)),
        make_link(
            sole_name,
            [
                SpherePart(
                    "sole_marker",
                    radius=0.008,
                    origin=(0.0, 0.0, 0.0),
                    mass=1.0e-4,
                    color=COLOR_SOLE,
                )
            ],
        ),
    ]

    joints_rad = params["joints_rad"]
    hip_origin = (params["hip_x"], y_sign * params["hip_y"], 0.0)
    stacked = (0.0, 0.0, -params["stacked_distance"])
    segment = (0.0, 0.0, -params["segment_distance"])
    label = "左" if side == "left" else "右"

    joints = [
        revolute(
            f"{side}_hip_roll",
            "basket",
            hip_name,
            hip_origin,
            roll_axis,
            joints_rad["hip_roll"],
            params,
            f"{label}股ロール。カゴ底面から股ロール軸まで。",
        ),
        revolute(
            f"{side}_hip_pitch",
            hip_name,
            thigh_name,
            stacked,
            pitch_axis,
            joints_rad["hip_pitch"],
            params,
            f"{label}股ピッチ。股ロール軸からサーボ1段分だけ下。",
        ),
        revolute(
            f"{side}_knee_pitch",
            thigh_name,
            shin_name,
            segment,
            pitch_axis,
            joints_rad["knee_pitch"],
            params,
            f"{label}膝。0 が伸び、正が後ろへの屈曲。",
        ),
        revolute(
            f"{side}_ankle_pitch",
            shin_name,
            ankle_name,
            segment,
            pitch_axis,
            joints_rad["ankle_pitch"],
            params,
            f"{label}足首ピッチ。膝から腿と同じ軸間距離だけ下。",
        ),
        revolute(
            f"{side}_ankle_roll",
            ankle_name,
            foot_name,
            stacked,
            roll_axis,
            joints_rad["ankle_roll"],
            params,
            f"{label}足首ロール。足首ピッチ軸からサーボ1段分だけ下。",
        ),
        Joint(
            name=f"{side}_sole_fixed",
            joint_type="fixed",
            parent=foot_name,
            child=sole_name,
            origin=(params["foot_center_x"], 0.0, -params["ankle_to_sole"]),
            comment=f"{label}足裏の下面中心。接触や接地判定の参照点。板の質量は {foot_name} 側。",
        ),
    ]
    return links, joints


def link_xml(link: Link) -> str:
    inertial = link.inertial
    assert inertial is not None
    lines = [f'  <link name="{link.name}">']
    lines.append("    <inertial>")
    lines.append(f'      <origin xyz="{vec3(inertial.origin)}" rpy="0 0 0"/>')
    lines.append(f'      <mass value="{fmt(inertial.mass)}"/>')
    lines.append(
        "      <inertia"
        f' ixx="{fmt(inertial.ixx)}" ixy="{fmt(inertial.ixy)}" ixz="{fmt(inertial.ixz)}"'
        f' iyy="{fmt(inertial.iyy)}" iyz="{fmt(inertial.iyz)}" izz="{fmt(inertial.izz)}"/>'
    )
    lines.append("    </inertial>")
    for index, part in enumerate(link.parts):
        lines.extend(_geometry_block("visual", link.name, index, part))
        if part.collision:
            lines.extend(_geometry_block("collision", link.name, index, part))
    lines.append("  </link>")
    return "\n".join(lines)


def _geometry_block(
    kind: str, link_name: str, index: int, part: BoxPart | SpherePart
) -> list[str]:
    """visual または collision。球には色だけ付け、collision は呼び出し側が省く。"""
    tag_name = f"{link_name}_{part.name}_{index}"
    lines = [f'    <{kind} name="{tag_name}">']
    lines.append(f'      <origin xyz="{vec3(part.origin)}" rpy="0 0 0"/>')
    lines.append("      <geometry>")
    if isinstance(part, BoxPart):
        lines.append(f'        <box size="{vec3(part.size)}"/>')
    else:
        lines.append(f'        <sphere radius="{fmt(part.radius)}"/>')
    lines.append("      </geometry>")
    if kind == "visual":
        lines.append("      <material>")
        lines.append(f'        <color rgba="{rgba(part.color)}"/>')
        lines.append("      </material>")
    lines.append(f"    </{kind}>")
    return lines


def joint_xml(joint: Joint) -> str:
    lines = []
    if joint.comment:
        lines.append(f"  <!-- {joint.comment} -->")
    lines.append(f'  <joint name="{joint.name}" type="{joint.joint_type}">')
    lines.append(f'    <parent link="{joint.parent}"/>')
    lines.append(f'    <child link="{joint.child}"/>')
    lines.append(f'    <origin xyz="{vec3(joint.origin)}" rpy="{vec3(joint.rpy)}"/>')
    if joint.joint_type == "revolute":
        assert joint.axis is not None
        lines.append(f'    <axis xyz="{vec3(joint.axis)}"/>')
        lines.append(
            "    <limit"
            f' lower="{fmt(joint.lower or 0.0)}"'
            f' upper="{fmt(joint.upper or 0.0)}"'
            f' effort="{fmt(joint.effort or 0.0)}"'
            f' velocity="{fmt(joint.velocity or 0.0)}"/>'
        )
        lines.append(
            f'    <dynamics damping="{fmt(joint.damping)}" friction="{fmt(joint.friction)}"/>'
        )
    lines.append("  </joint>")
    return "\n".join(lines)


def render_urdf(params: dict, links: list[Link], joints: list[Joint]) -> str:
    total_mass = sum(link.inertial.mass for link in links if link.inertial)
    sole_drop = standing_sole_drop(params)
    # カゴは原点より上に浮かせてある。天面は「下端 + 仕様の高さ」。
    basket_top = params["axis_inset"] + params["clearance"] + params["basket_size"][2]
    header = f"""<?xml version="1.0"?>
<!--
  {params["robot_name"]}
  generate_urdf.py が yuuki_biped.yaml から生成した。このファイルは手で編集しない。

  原点: 股ロール軸の高さ、左右中央。カゴの箱はその {fmt(params["axis_inset"] + params["clearance"])} m 上から始まる。
  x 前、y 左、z 上。ベースは地面に固定していない。
  股ロール軸: x={fmt(params["hip_x"])} m, y=±{fmt(params["hip_y"])} m
  サーボ軸間（板なし）: {fmt(params["stacked_distance"])} m
  腿・脛の軸間: {fmt(params["segment_distance"])} m
  直立時、原点から足裏まで: {fmt(sole_drop)} m
  直立時、足裏からカゴ天面まで: {fmt(sole_drop + basket_top)} m
  総質量（参照フレームの微小質量を含む）: {fmt(total_mass)} kg

  関節の原点は寸法式のまま。衝突箱は clearance だけ離し、サーボが板や電池や隣のサーボに入らない。
  股と足首のサーボは下端だけ短くして、次のサーボとのあいだに金具の隙間を空ける。
  ロール軸のサーボ（股ロール、足首ロール）はケースを 90 度回し、隣のピッチサーボと互い違いにする。
  電池はセル寸法ではなく、側板のあいだのダンボール。質量はセルのまま。
-->
<robot name="{params["robot_name"]}">
"""
    body = "\n".join(link_xml(link) for link in links)
    body += "\n"
    body += "\n".join(joint_xml(joint) for joint in joints)
    return header + body + "\n</robot>\n"


def standing_sole_drop(params: dict) -> float:
    """全関節 0 のとき、原点（股ロール軸の高さ）から足裏までの距離。下向きが正。"""
    return (
        2.0 * params["stacked_distance"]
        + 2.0 * params["segment_distance"]
        + params["ankle_to_sole"]
    )


def collect_warnings(params: dict) -> list[str]:
    """実測に差し替えるまで残す注意。重なりそのものは assert_boxes_clear が止める。"""
    warnings = []
    if abs(params["clearance"] - 0.004) < 1.0e-9:
        warnings.append(
            "clearance_m は未計測の 4 mm です。金具やダンボールの隙間を測ったら差し替えてください。"
        )
    return warnings


def assert_boxes_clear(links: list[Link], joints: list[Joint], tol: float = 1.0e-4) -> None:
    """全関節 0 で、衝突箱どうしが tol より深く食い込んでいないことを確かめる。

    同じリンクでも、関節の両側でも見る。PhysX が無視する組でも、形が重なると
    見た目と、あとから隣接衝突を入れたときの爆発が残る。球の目印は衝突を持たない。
    """
    origin: dict[str, tuple[float, float, float]] = {links[0].name: (0.0, 0.0, 0.0)}
    pending = list(joints)
    # 関節は親のあとに子が来るとは限らないので、親の位置が決まるまで繰り返す。
    guard = 0
    while pending:
        guard += 1
        if guard > len(joints) + 2:
            names = ", ".join(joint.child for joint in pending)
            raise RuntimeError(f"リンクの位置を決められません: {names}")
        still: list[Joint] = []
        for joint in pending:
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

    boxes: list[tuple[str, str, tuple[float, float, float], tuple[float, float, float]]] = []
    for link in links:
        base = origin[link.name]
        for part in link.parts:
            if not isinstance(part, BoxPart) or not part.collision:
                continue
            center = (
                base[0] + part.origin[0],
                base[1] + part.origin[1],
                base[2] + part.origin[2],
            )
            half = (part.size[0] / 2.0, part.size[1] / 2.0, part.size[2] / 2.0)
            low = (center[0] - half[0], center[1] - half[1], center[2] - half[2])
            high = (center[0] + half[0], center[1] + half[1], center[2] + half[2])
            boxes.append((link.name, part.name, low, high))

    hits: list[str] = []
    closest = 1.0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a_name, a_part, a_low, a_high = boxes[i]
            b_name, b_part, b_low, b_high = boxes[j]
            overlap = [
                min(a_high[axis], b_high[axis]) - max(a_low[axis], b_low[axis])
                for axis in range(3)
            ]
            # 離れている軸があれば、その軸の隙間がこの組の距離。
            # 1軸でも離れていれば食い込んでいない。その軸の隙間の最小を記録する。
            if min(overlap) <= tol:
                gaps = [-value for value in overlap if value <= 0.0]
                if gaps:
                    closest = min(closest, min(gaps))
                else:
                    closest = min(closest, 0.0)
                continue
            hits.append(
                f"  {a_name}/{a_part} と {b_name}/{b_part} が"
                f" x {overlap[0] * 1000:.1f} mm, y {overlap[1] * 1000:.1f} mm,"
                f" z {overlap[2] * 1000:.1f} mm 重なる"
            )
    if hits:
        raise RuntimeError("衝突箱が重なっています。\n" + "\n".join(hits))
    print(f"  collision_pairs {len(boxes) * (len(boxes) - 1) // 2}  closest_gap_m {closest:.4f}")


def check_written_urdf(path: Path, params: dict, link_count: int, joint_count: int) -> None:
    """書き出した XML が壊れていないか、関節数と質量だけ確認する。"""
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "robot":
        raise RuntimeError("ルート要素が robot ではありません")
    links = root.findall("link")
    joints = root.findall("joint")
    if len(links) != link_count or len(joints) != joint_count:
        raise RuntimeError(
            f"リンクまたは関節の数が一致しません: links {len(links)}/{link_count},"
            f" joints {len(joints)}/{joint_count}"
        )
    revolute = [joint for joint in joints if joint.get("type") == "revolute"]
    if len(revolute) != 10:
        raise RuntimeError(f"回転関節が 10 個ではありません: {len(revolute)}")
    mass = 0.0
    for link in links:
        mass_elem = link.find("./inertial/mass")
        if mass_elem is None or "value" not in mass_elem.attrib:
            raise RuntimeError(f"質量が無いリンクがあります: {link.get('name')}")
        mass += float(mass_elem.get("value", "0"))
    # レンダラと同じ合計になること。浮動小数の丸めだけ許容する。
    expected = sum(
        float(mass_elem.get("value", "0"))
        for mass_elem in root.findall("./link/inertial/mass")
    )
    if abs(mass - expected) > 1e-9:
        raise RuntimeError("質量の再集計に失敗しました")
    if mass < 1.0:
        raise RuntimeError(f"総質量が小さすぎます: {mass}")
    # 未使用でも、呼び出し側が渡したパラメータとファイル名が対応していることを示す。
    if root.get("name") != params["robot_name"]:
        raise RuntimeError("robot name がパラメータと一致しません")


def generate(config_path: Path, output_path: Path) -> None:
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    params = resolve_params(raw)
    links, joints = build_model(params)
    # 学習側の model_size が、この生成と違う足裏高さを読まないようにする。
    import model_size

    sole_drop = standing_sole_drop(params)
    if abs(sole_drop - model_size.SOLE_BELOW_ORIGIN_M) > 1.0e-9:
        raise RuntimeError(
            f"足裏高さが model_size と違います: 生成 {sole_drop:.6f},"
            f" model_size {model_size.SOLE_BELOW_ORIGIN_M:.6f}"
        )
    if abs((2.0 * params["hip_y"]) - model_size.HIP_SEPARATION_M) > 1.0e-9:
        raise RuntimeError("股の間隔が model_size と違います")
    leg_length = 2.0 * params["stacked_distance"] + 2.0 * params["segment_distance"]
    if abs(leg_length - model_size.LEG_LENGTH_HIP_TO_ANKLE_M) > 1.0e-9:
        raise RuntimeError("股から足首までの長さが model_size と違います")
    if abs(params["foot_size"][1] - model_size.PLATE_WIDTH_Y_M) > 1.0e-9:
        raise RuntimeError("足裏の左右幅が model_size と違います")
    # 書き出す前に、直立で箱が食い込んでいないことを止める。
    assert_boxes_clear(links, joints)
    output_path.write_text(render_urdf(params, links, joints), encoding="utf-8")
    check_written_urdf(output_path, params, len(links), len(joints))

    total_mass = sum(link.inertial.mass for link in links if link.inertial)
    sole_drop = standing_sole_drop(params)
    # カゴの天面は、浮かした下端に仕様の高さを足す。
    basket_top = params["axis_inset"] + params["clearance"] + params["basket_size"][2]
    height = sole_drop + basket_top
    print(f"wrote {output_path}")
    print(f"  stacked_servo_distance_m = {params['stacked_distance']:.4f}")
    print(f"  segment_axis_distance_m  = {params['segment_distance']:.4f}")
    print(f"  total_mass_kg            = {total_mass:.3f}")
    print(f"  sole_below_origin_m      = {sole_drop:.3f}")
    print(f"  sole_to_basket_top_m     = {height:.3f}")
    print("仮定のままの項目:")
    for key in ASSUMED_KEYS:
        print(f"  - {key}")
    for warning in collect_warnings(params):
        print(f"注意: {warning}")


def self_check_inertia() -> None:
    """箱1個の慣性と、左右対称な2質量の重心が原点になることを確認する。"""
    size = (0.2, 0.1, 0.4)
    mass = 2.0
    alone = combine_inertial(
        [BoxPart("only", size, (0.0, 0.0, 0.0), mass, COLOR_PLATE, False)]
    )
    expect = box_inertia_about_center(mass, size)
    if abs(alone.ixx - expect[0]) > 1e-12:
        raise RuntimeError("箱の ixx が公式と一致しません")
    if abs(alone.origin[0]) > 1e-12 or abs(alone.mass - mass) > 1e-12:
        raise RuntimeError("単一箱の重心または質量がずれています")

    pair = combine_inertial(
        [
            BoxPart("a", (0.01, 0.01, 0.01), (0.0, 0.05, 0.0), 1.0, COLOR_PLATE, False),
            BoxPart("b", (0.01, 0.01, 0.01), (0.0, -0.05, 0.0), 1.0, COLOR_PLATE, False),
        ]
    )
    if abs(pair.origin[1]) > 1e-12:
        raise RuntimeError("対称な2質量の重心が原点になりません")
    # 平行軸の定理: 各 1 kg が重心から 0.05 m。iyy には寄与せず、ixx と izz に m*dy^2 が足される。
    extra = 2.0 * (0.05 ** 2)
    base = box_inertia_about_center(1.0, (0.01, 0.01, 0.01))
    if abs(pair.ixx - (2.0 * base[0] + extra)) > 1e-12:
        raise RuntimeError("平行軸の定理の ixx が一致しません")


def main() -> int:
    parser = argparse.ArgumentParser(description="yuuki_biped.yaml から URDF を生成する")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="入力 YAML（既定: robot_description/yuuki_biped.yaml）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="出力 URDF（既定: robot_description/yuuki_biped.urdf）",
    )
    args = parser.parse_args()
    # Windows の既定コンソール（cp932）でも、注意書きの日本語が化けないようにする。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    self_check_inertia()
    generate(args.config, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
