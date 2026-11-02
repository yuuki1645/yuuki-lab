"""直立姿勢の部品リスト。

関節はハウジングの向きで示す。脚と腕のピッチは左右軸（円柱の軸が Y）、
首は鉛直軸（円柱の軸が Z）である。ロール用の別ハウジングはまだ無い。
ゼロ姿勢では脚も腕もまっすぐ下を向く。
"""

from __future__ import annotations

from dataclasses import dataclass

from humanoid.params import (
    ANKLE_JOINT_M,
    ANKLE_POST_RADIUS_M,
    ANKLE_Z_M,
    COLOR_FOOT,
    COLOR_HAND,
    COLOR_HEAD,
    COLOR_JOINT,
    COLOR_LIMB,
    COLOR_PELVIS,
    COLOR_TORSO,
    COLOR_VISOR,
    ELBOW_JOINT_M,
    ELBOW_Z_M,
    FOOT_CENTER_X_M,
    FOOT_LENGTH_M,
    FOOT_THICKNESS_M,
    FOOT_WIDTH_M,
    FOREARM_M,
    FOREARM_RADIUS_M,
    HAND_SIZE_M,
    HEAD_RADIUS_M,
    HIP_JOINT_M,
    HIP_Y_M,
    HIP_Z_M,
    KNEE_JOINT_M,
    NECK_LENGTH_M,
    NECK_RADIUS_M,
    NECK_TOP_Z_M,
    PELVIS_SIZE_M,
    SHIN_M,
    SHIN_RADIUS_M,
    SHOULDER_JOINT_M,
    SHOULDER_Y_M,
    SHOULDER_Z_M,
    THIGH_M,
    THIGH_RADIUS_M,
    TORSO_CENTER_Z_M,
    TORSO_SIZE_M,
    TORSO_TOP_Z_M,
    UPPER_ARM_M,
    UPPER_ARM_RADIUS_M,
    WRIST_Z_M,
    KNEE_Z_M,
)


@dataclass(frozen=True)
class PartSpec:
    """世界座標に置いた1部品。kind は box / zcyl / ycyl / sphere。"""

    name: str
    kind: str
    center_m: tuple[float, float, float]
    color: tuple[float, float, float, float]
    size_m: tuple[float, float, float] | None = None
    radius_m: float | None = None
    length_m: float | None = None


def _box(
    name: str,
    size: tuple[float, float, float],
    center: tuple[float, float, float],
    color: tuple[float, float, float, float],
) -> PartSpec:
    return PartSpec(name, "box", center, color, size_m=size)


def _cyl(
    name: str,
    axis: str,
    radius: float,
    length: float,
    center: tuple[float, float, float],
    color: tuple[float, float, float, float],
) -> PartSpec:
    """axis は 'y'（ピッチ軸）か 'z'（四肢と首）。"""
    if axis not in ("y", "z"):
        raise ValueError(f"軸は y か z です: {axis}")
    return PartSpec(name, f"{axis}cyl", center, color, radius_m=radius, length_m=length)


def _sphere(
    name: str,
    radius: float,
    center: tuple[float, float, float],
    color: tuple[float, float, float, float],
) -> PartSpec:
    return PartSpec(name, "sphere", center, color, radius_m=radius)


def _one_side(side_name: str, y_sign: float) -> list[PartSpec]:
    """片側。肩の y は股の y とは違うので、ここでは符号だけを渡す。"""
    hip_y = y_sign * HIP_Y_M
    shoulder_y = y_sign * SHOULDER_Y_M
    knee_z = KNEE_Z_M
    foot_z = FOOT_THICKNESS_M / 2.0
    post_length = ANKLE_Z_M - FOOT_THICKNESS_M
    post_z = FOOT_THICKNESS_M + post_length / 2.0
    # ヨークは胴の外側面と肩関節の中点。胴半幅と肩の y の平均に符号を付ける。
    yoke_y = y_sign * (TORSO_SIZE_M[1] / 2.0 + SHOULDER_Y_M) / 2.0
    return [
        _box(
            f"{side_name}_foot",
            (FOOT_LENGTH_M, FOOT_WIDTH_M, FOOT_THICKNESS_M),
            (FOOT_CENTER_X_M, hip_y, foot_z),
            COLOR_FOOT,
        ),
        _cyl(
            f"{side_name}_ankle_post",
            "z",
            ANKLE_POST_RADIUS_M,
            post_length,
            (0.0, hip_y, post_z),
            COLOR_LIMB,
        ),
        _cyl(
            f"{side_name}_ankle",
            "y",
            ANKLE_JOINT_M[0],
            ANKLE_JOINT_M[1],
            (0.0, hip_y, ANKLE_Z_M),
            COLOR_JOINT,
        ),
        _cyl(
            f"{side_name}_shin",
            "z",
            SHIN_RADIUS_M,
            SHIN_M,
            (0.0, hip_y, (ANKLE_Z_M + knee_z) / 2.0),
            COLOR_LIMB,
        ),
        _cyl(
            f"{side_name}_knee",
            "y",
            KNEE_JOINT_M[0],
            KNEE_JOINT_M[1],
            (0.0, hip_y, knee_z),
            COLOR_JOINT,
        ),
        _cyl(
            f"{side_name}_thigh",
            "z",
            THIGH_RADIUS_M,
            THIGH_M,
            (0.0, hip_y, (knee_z + HIP_Z_M) / 2.0),
            COLOR_LIMB,
        ),
        _cyl(
            f"{side_name}_hip",
            "y",
            HIP_JOINT_M[0],
            HIP_JOINT_M[1],
            (0.0, hip_y, HIP_Z_M),
            COLOR_JOINT,
        ),
        _box(
            f"{side_name}_shoulder_yoke",
            (0.090, 0.070, 0.090),
            (0.0, yoke_y, SHOULDER_Z_M),
            COLOR_TORSO,
        ),
        _cyl(
            f"{side_name}_shoulder",
            "y",
            SHOULDER_JOINT_M[0],
            SHOULDER_JOINT_M[1],
            (0.0, shoulder_y, SHOULDER_Z_M),
            COLOR_JOINT,
        ),
        _cyl(
            f"{side_name}_upper_arm",
            "z",
            UPPER_ARM_RADIUS_M,
            UPPER_ARM_M,
            (0.0, shoulder_y, (SHOULDER_Z_M + ELBOW_Z_M) / 2.0),
            COLOR_LIMB,
        ),
        _cyl(
            f"{side_name}_elbow",
            "y",
            ELBOW_JOINT_M[0],
            ELBOW_JOINT_M[1],
            (0.0, shoulder_y, ELBOW_Z_M),
            COLOR_JOINT,
        ),
        _cyl(
            f"{side_name}_forearm",
            "z",
            FOREARM_RADIUS_M,
            FOREARM_M,
            (0.0, shoulder_y, (ELBOW_Z_M + WRIST_Z_M) / 2.0),
            COLOR_LIMB,
        ),
        _box(
            f"{side_name}_hand",
            HAND_SIZE_M,
            (0.0, shoulder_y, WRIST_Z_M - HAND_SIZE_M[2] / 2.0),
            COLOR_HAND,
        ),
    ]


def standing_parts() -> list[PartSpec]:
    """頭、胴、両脚、両腕。原点は床、両足の中央。"""
    head_z = NECK_TOP_Z_M + HEAD_RADIUS_M
    neck_z = (TORSO_TOP_Z_M + NECK_TOP_Z_M) / 2.0
    parts = [
        _box("pelvis", PELVIS_SIZE_M, (0.0, 0.0, HIP_Z_M), COLOR_PELVIS),
        _box("torso", TORSO_SIZE_M, (0.0, 0.0, TORSO_CENTER_Z_M), COLOR_TORSO),
        _cyl("neck", "z", NECK_RADIUS_M, NECK_LENGTH_M, (0.0, 0.0, neck_z), COLOR_LIMB),
        _sphere("head", HEAD_RADIUS_M, (0.0, 0.0, head_z), COLOR_HEAD),
        # 顔の前面に薄い板。球の表面に半分埋め、頭頂は越えない。
        _box(
            "visor",
            (0.012, 0.100, 0.060),
            (HEAD_RADIUS_M, 0.0, head_z - 0.010),
            COLOR_VISOR,
        ),
    ]
    parts.extend(_one_side("left", 1.0))
    parts.extend(_one_side("right", -1.0))
    return parts
