# servo.py
from __future__ import annotations
from kinematics import KINEMATICS

HARDWARE_ENABLED = True

PHYSICAL_MIN = 0.0
PHYSICAL_MAX = 270.0

pca = None
if HARDWARE_ENABLED:
    try:
        import busio
        from board import SCL, SDA
        from adafruit_pca9685 import PCA9685

        i2c = busio.I2C(SCL, SDA)
        pca = PCA9685(i2c)
        pca.frequency = 333
    except Exception as e:
        print("[WARN] PCA9685 init failed:", e)
        HARDWARE_ENABLED = False
        pca = None

SERVO_MAP = {
    "R_HIP1": 0,
    "R_HIP2": 1,
    "R_KNEE": 2,
    "R_HEEL": 3,
    "L_HIP1": 8,
    "L_HIP2": 9,
    "L_KNEE": 10,
    "L_HEEL": 11,
}

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def physical_angle_to_duty(physical_deg: float) -> int:
    if pca is None:
        raise RuntimeError("PCA9685 not initialized")

    deg = clamp(float(physical_deg), PHYSICAL_MIN, PHYSICAL_MAX)

    min_us = 500
    max_us = 2500
    us = min_us + (deg / 270.0) * (max_us - min_us)

    period_us = 1_000_000 / pca.frequency
    return int((us / period_us) * 0xFFFF)

def _apply_physical(servo_name: str, physical_angle: float) -> dict:
    """物理角を実機へ適用（SIM時も同じ戻り形式）"""
    if servo_name not in SERVO_MAP:
        raise ValueError(f"Unknown servo: {servo_name}")

    physical_f = float(physical_angle)

    if not HARDWARE_ENABLED:
        print(f"[SIM] {servo_name}: physical={physical_f:.1f}")
        return {"servo": servo_name, "physical": physical_f, "sim": True}

    ch = SERVO_MAP[servo_name]
    duty = physical_angle_to_duty(physical_f)
    pca.channels[ch].duty_cycle = duty
    return {"servo": servo_name, "physical": physical_f, "channel": ch, "sim": False}

def move_servo_physical(servo_name: str, physical_angle: float) -> dict:
    """物理角モード：物理角をそのまま指定"""
    return _apply_physical(servo_name, clamp(float(physical_angle), PHYSICAL_MIN, PHYSICAL_MAX))

def move_servo_logical(servo_name: str, logical_angle: float) -> dict:
    """論理角モード：論理角→物理角へ変換して指定"""
    if servo_name not in KINEMATICS:
        raise ValueError(f"No kinematics for servo: {servo_name}")

    kin = KINEMATICS[servo_name]
    logical = float(logical_angle)

    physical = kin.logical_to_physical(logical)
    if physical is None:
        raise RuntimeError(
            f"Kinematics returned None: servo={servo_name}, logical={logical}, kin={type(kin).__name__}"
        )

    physical_f = float(physical)
    result = _apply_physical(servo_name, physical_f)
    return {"servo": servo_name, "logical": logical, **result}
