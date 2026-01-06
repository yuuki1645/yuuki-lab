# servo.py
import time

HARDWARE_ENABLED = True

ANGLE_MIN = 0
ANGLE_MAX = 270

# ===== PCA9685 初期化 =====
pca = None
if HARDWARE_ENABLED:
    try:
        import busio
        from board import SCL, SDA
        from adafruit_pca9685 import PCA9685

        i2c = busio.I2C(SCL, SDA)
        pca = PCA9685(i2c)
        pca.frequency = 333  # ★ 必要なら変更
    except Exception as e:
        print("[WARN] PCA9685 init failed:", e)
        HARDWARE_ENABLED = False


# ===== サーボ定義 =====
# ★ チャンネルはここだけ編集すればOK
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


def angle_to_duty(angle: float) -> int:
    """0–270° → PCA9685 duty"""
    angle = max(ANGLE_MIN, min(ANGLE_MAX, angle))
    min_us = 500
    max_us = 2500
    us = min_us + (angle / 270.0) * (max_us - min_us)

    period_us = 1_000_000 / pca.frequency
    duty = int((us / period_us) * 0xFFFF)
    return duty


def move_servo(servo_name: str, angle: float):
    if servo_name not in SERVO_MAP:
        raise ValueError("Unknown servo")

    if not HARDWARE_ENABLED:
        print(f"[SIM] {servo_name} -> {angle}°")
        return

    ch = SERVO_MAP[servo_name]
    duty = angle_to_duty(angle)
    pca.channels[ch].duty_cycle = duty
