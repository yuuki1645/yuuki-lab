# kinematics.py
from __future__ import annotations
from dataclasses import dataclass

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class LogicalRange:
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

    def __init__(self, name: str, logical_lo: float, logical_hi: float):
        self.name = name
        self.logical_range = LogicalRange(logical_lo, logical_hi)

    def clamp_logical(self, logical_deg: float) -> float:
        return clamp(float(logical_deg), self.logical_range.lo, self.logical_range.hi)

    def logical_to_physical(self, logical_deg: float) -> float:
        raise NotImplementedError


# ----------------------------
# 論理角レンジ（あなた確定）
# ----------------------------
RANGE_HEEL = (-30.0,  90.0)
RANGE_KNEE = (  0.0, 120.0)
RANGE_HIP1 = (-30.0,  90.0)
RANGE_HIP2 = (-30.0, 120.0)


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
        super().__init__("R_HEEL", *RANGE_HEEL)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l + 90.0


class RKneeKinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("R_KNEE", *RANGE_KNEE)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l + 90.0


class RHip1Kinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("R_HIP1", *RANGE_HIP1)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l


class RHip2Kinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("R_HIP2", *RANGE_HIP2)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

class LHeelKinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("L_HEEL", *RANGE_HEEL)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l


class LKneeKinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("L_KNEE", *RANGE_KNEE)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l


class LHip1Kinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("L_HIP1", *RANGE_HIP1)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

class LHip2Kinematics(ServoKinematicsBase):
    def __init__(self):
        super().__init__("L_HIP2", *RANGE_HIP2)

    def logical_to_physical(self, logical_deg: float) -> float:
        l = self.clamp_logical(logical_deg)
        return l

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
