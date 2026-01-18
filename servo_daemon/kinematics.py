# kinematics.py
from __future__ import annotations
from dataclasses import dataclass

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class LogicalRange:
    lo: float
    hi: float

@dataclass(frozen=True)
class PhysicalRange:
    lo: float
    hi: float

class ServoKinematicsBase:
    """
    1サーボ個体の「論理角 -> 物理角」変換。
    - 論理角レンジを持つ
    - logical_to_physical() を各サーボで自由に実装
    """
    name: str
    logical_range: LogicalRange
    physical_range: PhysicalRange
    default_logical: float

    def __init__(
        self,
        name: str,
        logical_lo: float,
        logical_hi: float,
        physical_lo: float,
        physical_hi: float,
        default_logical: float,
    ):
        self.name = name
        self.logical_range = LogicalRange(logical_lo, logical_hi)
        self.physical_range = PhysicalRange(physical_lo, physical_hi)
        self.default_logical = default_logical

    def clamp_logical(self, logical_deg: float) -> float:
        return clamp(float(logical_deg), self.logical_range.lo, self.logical_range.hi)

    def logical_to_physical(self, logical_deg: float) -> float:
        raise NotImplementedError

    def physical_to_logical(self, physical_deg: float) -> float:
        raise NotImplementedError

    @property
    def default_physical(self):
        return self.logical_to_physical(self.default_logical)


# ----------------------------
# 論理角レンジ・物理角レンジ
# ----------------------------
LOGICAL_RANGE_HEEL = (-30.0,  90.0)
LOGICAL_RANGE_KNEE = (  0.0, 120.0)
LOGICAL_RANGE_HIP1 = (-30.0,  90.0)
LOGICAL_RANGE_HIP2 = (-30.0, 120.0)
PHYSICAL_RANGE_HEEL = (0.0, 270.0)
PHYSICAL_RANGE_KNEE = (0.0, 270.0)
PHYSICAL_RANGE_HIP1 = (0.0, 270.0)
PHYSICAL_RANGE_HIP2 = (0.0, 270.0)
DEFAULT_LOGICAL_HEEL = -30.0
DEFAULT_LOGICAL_KNEE = 30.0
DEFAULT_LOGICAL_HIP1 = 0.0
DEFAULT_LOGICAL_HIP2 = 60.0


# ============================================================
# ★ 8つの「個別クラス」を生成（冗長OK版）
#   ここから先は、各サーボごとに
#   - クランプ
#   - オフセット
#   - 反転
#   - 非線形（必要なら）
#   を好きに書ける
# ============================================================

class RHeelKinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("R_HEEL", *LOGICAL_RANGE_HEEL, *PHYSICAL_RANGE_HEEL, DEFAULT_LOGICAL_HEEL)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l + 100.0

    def physical_to_logical(self, physical_deg: float) -> float:
        return physical_deg - 90.0


class RKneeKinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("R_KNEE", *LOGICAL_RANGE_KNEE, *PHYSICAL_RANGE_KNEE, DEFAULT_LOGICAL_KNEE)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l + 93.0

    def physical_to_logical(self, physical_deg: float) -> float:
        return physical_deg - 93.0


class RHip1Kinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("R_HIP1", *LOGICAL_RANGE_HIP1, *PHYSICAL_RANGE_HIP1, DEFAULT_LOGICAL_HIP1)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l + 70.0

    def physical_to_logical(self, physical_deg: float) -> float:
        return physical_deg - 70.0


class RHip2Kinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("R_HIP2", *LOGICAL_RANGE_HIP2, *PHYSICAL_RANGE_HIP2, DEFAULT_LOGICAL_HIP2)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return 200.0 - l

    def physical_to_logical(self, physical_deg: float) -> float:
        return 200.0 - physical_deg


class LHeelKinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("L_HEEL", *LOGICAL_RANGE_HEEL, *PHYSICAL_RANGE_HEEL, DEFAULT_LOGICAL_HEEL)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l + 65.0

    def physical_to_logical(self, physical_deg: float) -> float:
        return physical_deg - 65.0


class LKneeKinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("L_KNEE", *LOGICAL_RANGE_KNEE, *PHYSICAL_RANGE_KNEE, DEFAULT_LOGICAL_KNEE)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l + 90.0

    def physical_to_logical(self, physical_deg: float) -> float:
        return physical_deg - 90.0


class LHip1Kinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("L_HIP1", *LOGICAL_RANGE_HIP1, *PHYSICAL_RANGE_HIP1, DEFAULT_LOGICAL_HIP1)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l + 95.0

    def physical_to_logical(self, physical_deg: float) -> float:
        return physical_deg - 95.0


class LHip2Kinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("L_HIP2", *LOGICAL_RANGE_HIP2, *PHYSICAL_RANGE_HIP2, DEFAULT_LOGICAL_HIP2)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return 164.0 - l

    def physical_to_logical(self, physical_deg: float) -> float:
        return 164.0 - physical_deg

# ★ 8インスタンスを生成して辞書へ
KINEMATICS = {
    "R_HEEL": RHeelKinematics(),
    "R_KNEE": RKneeKinematics(),
    "R_HIP1": RHip1Kinematics(),
    "R_HIP2": RHip2Kinematics(),
    "L_HEEL": LHeelKinematics(),
    "L_KNEE": LKneeKinematics(),
    "L_HIP1": LHip1Kinematics(),
    "L_HIP2": LHip2Kinematics(),
}
