# type: ignore
# ruff: noqa: E741  # robot-daemon/kinematics.py に合わせて `l` を logical の略として使う

"""論理角(度) ⇄ MuJoCo 関節角(度) の変換テーブル。

robot-daemon の `kinematics.py` と同じ思想で、サーボ毎に独立したクラスで
「論理角 → MuJoCo 関節角」の式を直書きする。共通ヘルパで生成しないので、
読み違えやコピペミスは「そのクラスの 2 メソッドだけ」を見れば検出できる。

- 各サーボ毎の式は `logical_to_mujoco_deg(logical)` と `mujoco_deg_to_logical(mujoco)` の対。
- どちらか一方だけ書き換えると逆写像が壊れるので、**必ず両方を同時に直す**こと。
- 値は実機（robot-daemon/kinematics.py）と Viewer の目視で校正してください。
  初期値は「立ち姿勢で MuJoCo qpos=0 になる」よう offset を入れた最低限の構成。
"""

from __future__ import annotations

from dataclasses import dataclass


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class LogicalRange:
    lo: float
    hi: float


class JointKinematicsBase:
    """1 サーボ個体の「論理角(度) ⇄ MuJoCo 関節角(度)」変換のベース。

    各サーボで `logical_to_mujoco_deg` と `mujoco_deg_to_logical` を直に実装する。
    `actuator` は MJCF の position アクチュエータ名（/api/set のキー）、
    `joint` は MJCF の hinge 関節名（/api/state hinge_joint_rad のキー）。
    """

    actuator: str
    joint: str
    logical_range: LogicalRange
    default_logical: float

    def __init__(
        self,
        actuator: str,
        joint: str,
        logical_lo: float,
        logical_hi: float,
        default_logical: float,
    ):
        self.actuator = actuator
        self.joint = joint
        self.logical_range = LogicalRange(logical_lo, logical_hi)
        self.default_logical = default_logical

    def clamp_logical(self, logical_deg: float) -> float:
        return clamp(
            float(logical_deg), self.logical_range.lo, self.logical_range.hi
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        raise NotImplementedError

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        raise NotImplementedError

    @property
    def default_mujoco_deg(self) -> float:
        return self.logical_to_mujoco_deg(self.default_logical)


# ----------------------------
# 論理角レンジ・デフォルト
# （robot-daemon/kinematics.py と同値。「実機の論理角」体系）
# ----------------------------
LOGICAL_RANGE_HEEL = (-50.0, 90.0)
LOGICAL_RANGE_HEEL_ROLL = (-20.0, 20.0)
LOGICAL_RANGE_KNEE = (0.0, 120.0)
LOGICAL_RANGE_HIP1 = (-30.0, 90.0)
LOGICAL_RANGE_HIP2 = (-30.0, 120.0)

DEFAULT_LOGICAL_HEEL = -30.0
DEFAULT_LOGICAL_HEEL_ROLL = 0.0
DEFAULT_LOGICAL_KNEE = 30.0
DEFAULT_LOGICAL_HIP1 = 0.0
DEFAULT_LOGICAL_HIP2 = 60.0


# ============================================================
# ★ 10 関節分の「個別クラス」を直書き（robot-daemon と同じ流儀）
#   ここから先は、各サーボごとに
#   - クランプ
#   - オフセット
#   - 反転
#   - 非線形（必要なら）
#   を好きに書ける。共通ヘルパで生成しない。
# ============================================================


# ---------- Left ----------

class LHip1Kinematics(JointKinematicsBase):
    """L_HIP1（hip_roll）: 立ち姿勢で logical 0° = MuJoCo 0°（恒等）"""

    def __init__(self):
        super().__init__(
            "left_hip_roll_motor", "left_hip_roll",
            *LOGICAL_RANGE_HIP1, DEFAULT_LOGICAL_HIP1,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return mujoco_deg


class LHip2Kinematics(JointKinematicsBase):
    """L_HIP2（hip_pitch）: 立ち姿勢で logical 60° = MuJoCo 0°"""

    def __init__(self):
        super().__init__(
            "left_hip_pitch_motor", "left_hip_pitch",
            *LOGICAL_RANGE_HIP2, DEFAULT_LOGICAL_HIP2,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l - 90.0

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return mujoco_deg + 90.0


class LKneeKinematics(JointKinematicsBase):
    """L_KNEE（knee_pitch）: 立ち姿勢で logical 30° = MuJoCo 0°"""

    def __init__(self):
        super().__init__(
            "left_knee_pitch_motor", "left_knee_pitch",
            *LOGICAL_RANGE_KNEE, DEFAULT_LOGICAL_KNEE,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return mujoco_deg


class LHeelKinematics(JointKinematicsBase):
    """L_HEEL（ankle_pitch）: 立ち姿勢で logical -30° = MuJoCo 0°"""

    def __init__(self):
        super().__init__(
            "left_ankle_pitch_motor", "left_ankle_pitch",
            *LOGICAL_RANGE_HEEL, DEFAULT_LOGICAL_HEEL,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return mujoco_deg


class LHeelRollKinematics(JointKinematicsBase):
    """L_HEEL_ROLL（ankle_roll）: 立ち姿勢で logical 0° = MuJoCo 0°（恒等）"""

    def __init__(self):
        super().__init__(
            "left_ankle_roll_motor", "left_ankle_roll",
            *LOGICAL_RANGE_HEEL_ROLL, DEFAULT_LOGICAL_HEEL_ROLL,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return mujoco_deg


# ---------- Right ----------
# 左右で MJCF の `axis` が同じ場合、roll 系は物理的な向きが反転するため符号反転。
# pitch 系（hip2 / knee / heel）は左右で同じ符号に揃えている（要 Viewer 校正）。

class RHip1Kinematics(JointKinematicsBase):
    """R_HIP1（hip_roll）: logical 正で外転になるよう左右反転（MJCF の axis が左と同じ "1 0 0" のため）"""

    def __init__(self):
        super().__init__(
            "right_hip_roll_motor", "right_hip_roll",
            *LOGICAL_RANGE_HIP1, DEFAULT_LOGICAL_HIP1,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return -l

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return -mujoco_deg


class RHip2Kinematics(JointKinematicsBase):
    """R_HIP2（hip_pitch）: 立ち姿勢で logical 60° = MuJoCo 0°"""

    def __init__(self):
        super().__init__(
            "right_hip_pitch_motor", "right_hip_pitch",
            *LOGICAL_RANGE_HIP2, DEFAULT_LOGICAL_HIP2,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l - 90.0

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return mujoco_deg + 90.0


class RKneeKinematics(JointKinematicsBase):
    """R_KNEE（knee_pitch）: 立ち姿勢で logical 30° = MuJoCo 0°"""

    def __init__(self):
        super().__init__(
            "right_knee_pitch_motor", "right_knee_pitch",
            *LOGICAL_RANGE_KNEE, DEFAULT_LOGICAL_KNEE,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return mujoco_deg


class RHeelKinematics(JointKinematicsBase):
    """R_HEEL（ankle_pitch）: 立ち姿勢で logical -30° = MuJoCo 0°"""

    def __init__(self):
        super().__init__(
            "right_ankle_pitch_motor", "right_ankle_pitch",
            *LOGICAL_RANGE_HEEL, DEFAULT_LOGICAL_HEEL,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return mujoco_deg


class RHeelRollKinematics(JointKinematicsBase):
    """R_HEEL_ROLL（ankle_roll）: 左右で MJCF axis が同じため符号反転"""

    def __init__(self):
        super().__init__(
            "right_ankle_roll_motor", "right_ankle_roll",
            *LOGICAL_RANGE_HEEL_ROLL, DEFAULT_LOGICAL_HEEL_ROLL,
        )

    def logical_to_mujoco_deg(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return -l

    def mujoco_deg_to_logical(self, mujoco_deg: float) -> float:
        return -mujoco_deg


# ★ インスタンスを生成して辞書へ（キーはアクチュエータ名）
KINEMATICS: dict[str, JointKinematicsBase] = {
    "left_hip_roll_motor": LHip1Kinematics(),
    "left_hip_pitch_motor": LHip2Kinematics(),
    "left_knee_pitch_motor": LKneeKinematics(),
    "left_ankle_pitch_motor": LHeelKinematics(),
    "left_ankle_roll_motor": LHeelRollKinematics(),
    "right_hip_roll_motor": RHip1Kinematics(),
    "right_hip_pitch_motor": RHip2Kinematics(),
    "right_knee_pitch_motor": RKneeKinematics(),
    "right_ankle_pitch_motor": RHeelKinematics(),
    "right_ankle_roll_motor": RHeelRollKinematics(),
}


def kinematics_by_joint() -> dict[str, JointKinematicsBase]:
    """MJCF の joint 名 → 対応 kinematics の逆引き辞書。"""
    return {kin.joint: kin for kin in KINEMATICS.values()}
