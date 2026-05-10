# type: ignore

"""論理角(度) ⇄ MuJoCo 関節角(度) の変換テーブル。

robot-daemon の `kinematics.py` と同じ思想で、サーボ毎に独立した
`logical → mujoco` の写像を持つ。MJCF の axis や建造姿勢を素のまま保ったうえで、
フロント（ポーズエディタ）からの「論理角」を MuJoCo の関節角に揃えるためのレイヤ。

写像はサーボ単位の **線形変換**（offset + sign）。非線形な機構が必要になったら、
`logical_to_mujoco_deg` を関数で差し替える形に拡張する。

各値は実機（robot-daemon/kinematics.py）と Viewer の目視で校正してください。
初期値は「立ち姿勢で MuJoCo qpos=0 になる」よう offset を入れた最低限の構成です。
"""

from __future__ import annotations

from dataclasses import dataclass


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class JointKinematics:
    """1 関節分の論理⇄MuJoCo 写像。

    Attributes:
        actuator: MJCF の position アクチュエータ名（/api/set のキー）。
        joint:    MJCF の hinge 関節名（/api/state hinge_joint_rad のキー）。
        sign:     +1 または -1。論理角を増やしたとき MuJoCo qpos が増える向きが +1。
        offset_deg: ``mujoco_deg = sign * logical_deg + offset_deg`` の offset。
        logical_lo, logical_hi: 論理角のクランプ範囲（度）。
        default_logical: そのサーボのデフォルト論理角（フロントの初期表示用）。
    """

    actuator: str
    joint: str
    sign: int
    offset_deg: float
    logical_lo: float
    logical_hi: float
    default_logical: float

    def __post_init__(self) -> None:
        if self.sign not in (-1, 1):
            raise ValueError(f"sign must be +1 or -1 (got {self.sign})")

    def clamp_logical(self, logical_deg: float) -> float:
        return _clamp(float(logical_deg), self.logical_lo, self.logical_hi)

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        clamped = self.clamp_logical(logical_deg)
        return self.sign * clamped + self.offset_deg

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return (float(mujoco_deg) - self.offset_deg) / self.sign


# robot-daemon/kinematics.py と同じ論理レンジ・デフォルトを基準にしている。
# サインとオフセットは「立ち姿勢（MuJoCo qpos=0）で各サーボの default_logical を取る」を
# 満たすように初期化している。**符号は MJCF の axis 方向に依存** するので、
# Viewer で目視確認のうえ -1/+1 を入れ替えて校正してください。

_LOGICAL_RANGE_HEEL = (-50.0, 90.0)
_LOGICAL_RANGE_HEEL_ROLL = (-20.0, 20.0)
_LOGICAL_RANGE_KNEE = (0.0, 120.0)
_LOGICAL_RANGE_HIP1 = (-30.0, 90.0)
_LOGICAL_RANGE_HIP2 = (-30.0, 120.0)

_DEFAULT_HEEL = -30.0
_DEFAULT_HEEL_ROLL = 0.0
_DEFAULT_KNEE = 30.0
_DEFAULT_HIP1 = 0.0
_DEFAULT_HIP2 = 60.0


def _kin(
    actuator: str,
    joint: str,
    sign: int,
    logical_range: tuple[float, float],
    default_logical: float,
) -> JointKinematics:
    """`logical = default_logical` のとき MuJoCo qpos = 0 になるよう offset を設定する。"""
    offset_deg = -sign * default_logical
    return JointKinematics(
        actuator=actuator,
        joint=joint,
        sign=sign,
        offset_deg=offset_deg,
        logical_lo=logical_range[0],
        logical_hi=logical_range[1],
        default_logical=default_logical,
    )


KINEMATICS: dict[str, JointKinematics] = {
    # ----- Left -----
    "left_hip_roll_motor": _kin(
        "left_hip_roll_motor", "left_hip_roll",
        sign=+1, logical_range=_LOGICAL_RANGE_HIP1, default_logical=_DEFAULT_HIP1,
    ),
    "left_hip_pitch_motor": _kin(
        "left_hip_pitch_motor", "left_hip_pitch",
        sign=+1, logical_range=_LOGICAL_RANGE_HIP2, default_logical=_DEFAULT_HIP2,
    ),
    "left_knee_pitch_motor": _kin(
        "left_knee_pitch_motor", "left_knee_pitch",
        sign=+1, logical_range=_LOGICAL_RANGE_KNEE, default_logical=_DEFAULT_KNEE,
    ),
    "left_ankle_pitch_motor": _kin(
        "left_ankle_pitch_motor", "left_ankle_pitch",
        sign=+1, logical_range=_LOGICAL_RANGE_HEEL, default_logical=_DEFAULT_HEEL,
    ),
    "left_ankle_roll_motor": _kin(
        "left_ankle_roll_motor", "left_ankle_roll",
        sign=+1, logical_range=_LOGICAL_RANGE_HEEL_ROLL, default_logical=_DEFAULT_HEEL_ROLL,
    ),
    # ----- Right（左右で MJCF axis が同じ場合は sign を反転して合わせる）-----
    "right_hip_roll_motor": _kin(
        "right_hip_roll_motor", "right_hip_roll",
        sign=-1, logical_range=_LOGICAL_RANGE_HIP1, default_logical=_DEFAULT_HIP1,
    ),
    "right_hip_pitch_motor": _kin(
        "right_hip_pitch_motor", "right_hip_pitch",
        sign=+1, logical_range=_LOGICAL_RANGE_HIP2, default_logical=_DEFAULT_HIP2,
    ),
    "right_knee_pitch_motor": _kin(
        "right_knee_pitch_motor", "right_knee_pitch",
        sign=+1, logical_range=_LOGICAL_RANGE_KNEE, default_logical=_DEFAULT_KNEE,
    ),
    "right_ankle_pitch_motor": _kin(
        "right_ankle_pitch_motor", "right_ankle_pitch",
        sign=+1, logical_range=_LOGICAL_RANGE_HEEL, default_logical=_DEFAULT_HEEL,
    ),
    "right_ankle_roll_motor": _kin(
        "right_ankle_roll_motor", "right_ankle_roll",
        sign=-1, logical_range=_LOGICAL_RANGE_HEEL_ROLL, default_logical=_DEFAULT_HEEL_ROLL,
    ),
}


def kinematics_by_joint() -> dict[str, JointKinematics]:
    """MJCF の joint 名 → JointKinematics の逆引き辞書。"""
    return {kin.joint: kin for kin in KINEMATICS.values()}
