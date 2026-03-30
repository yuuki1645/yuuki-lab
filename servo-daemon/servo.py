
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
    "R_HEEL_ROLL": 4,
    "L_HIP1": 8,
    "L_HIP2": 9,
    "L_KNEE": 10,
    "L_HEEL": 11,
    "L_HEEL_ROLL": 12,
}

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def physical_angle_to_duty(physical_angle: float):
    if pca is None:
        raise RuntimeError("PCA9685 not initialized")

    deg = clamp(float(physical_angle), PHYSICAL_MIN, PHYSICAL_MAX)

    min_us = 500
    max_us = 2500
    us = min_us + (deg / 270.0) * (max_us - min_us)

    period_us = 1_000_000 / pca.frequency
    return int((us / period_us) * 0xFFFF)

def _apply_physical(servo_name: str, physical_angle: float):
    """物理角を実機へ適用（単一サーボ）"""
    if servo_name not in SERVO_MAP:
        raise ValueError(f"Unknown servo: {servo_name}")

    if not HARDWARE_ENABLED:
        print(f"[SIM] {servo_name}: physical={physical_angle:.1f}")
        return

    ch = SERVO_MAP[servo_name]
    duty = physical_angle_to_duty(physical_angle)
    pca.channels[ch].duty_cycle = duty

def _apply_physical_multiple(servo_angles: dict[str, float]):
    """
    複数のサーボの物理角を一括適用
    
    Args:
        servo_angles: {servo_name: physical_angle} の形式
    
    Returns:
        {servo_name: {"ch": ch, "logical": logical, "physical": physical}} の形式
    """
    results = {}
    
    if not HARDWARE_ENABLED:
        # シミュレーションモード：論理角を計算して results に格納
        for servo_name, physical_angle in servo_angles.items():
            if servo_name not in SERVO_MAP:
                continue
            if servo_name in KINEMATICS:
                kin = KINEMATICS[servo_name]
                logical_angle = kin.physical_to_logical(physical_angle)
                results[servo_name] = {
                    "ch": SERVO_MAP[servo_name],
                    "logical": logical_angle,
                    "physical": physical_angle
                }
        
        # 表形式で論理角を出力（HIP1/HIP2/KNEE/HEEL × R/L）
        if results:
            JOINTS = ["HIP1", "HIP2", "KNEE", "HEEL", "HEEL_ROLL"]
            SIDES = ["R", "L"]
            COL_WIDTH = 10
            header = " " * 2 + "".join(j.rjust(COL_WIDTH) for j in JOINTS)
            print(f"[SIM]\n{header}")
            for side in SIDES:
                row_parts = [f"{side:>2}"]
                for joint in JOINTS:
                    name = f"{side}_{joint}"
                    logical = results.get(name, {}).get("logical")
                    if logical is not None:
                        row_parts.append(f"{round(logical):>{COL_WIDTH}}")
                    else:
                        row_parts.append(f"{'--':>{COL_WIDTH}}")
                print("".join(row_parts))
        
        return results
    
    # 実機モード：全サーボのduty_cycleを計算してから一括設定
    duty_updates = {}
    for servo_name, physical_angle in servo_angles.items():
        if servo_name not in SERVO_MAP:
            continue
        
        ch = SERVO_MAP[servo_name]
        duty = physical_angle_to_duty(physical_angle)
        duty_updates[ch] = duty
        
        # 論理角も計算
        if servo_name in KINEMATICS:
            kin = KINEMATICS[servo_name]
            logical_angle = kin.physical_to_logical(physical_angle)
            results[servo_name] = {
                "ch": ch,
                "logical": logical_angle,
                "physical": physical_angle
            }
    
    # 一括でduty_cycleを設定
    for ch, duty in duty_updates.items():
        pca.channels[ch].duty_cycle = duty
    
    return results

def move_servo_physical(servo_name: str, physical_angle: float):
    """物理角モード：物理角をそのまま指定（単一サーボ）"""
    if servo_name not in KINEMATICS:
        raise ValueError(f"No kinematics for servo: {servo_name}")
    
    kin = KINEMATICS[servo_name]
    logical_angle = kin.physical_to_logical(physical_angle)
    _apply_physical(servo_name, physical_angle)

    return {
        "servo": servo_name,
        "ch": SERVO_MAP[servo_name],
        "logical": logical_angle,
        "physical": physical_angle
    }

def move_servo_logical(servo_name: str, logical_angle: float):
    """論理角モード：論理角→物理角へ変換して指定（単一サーボ）"""
    if servo_name not in KINEMATICS:
        raise ValueError(f"No kinematics for servo: {servo_name}")

    kin = KINEMATICS[servo_name]
    physical_angle = kin.logical_to_physical(logical_angle)
    _apply_physical(servo_name, physical_angle)

    return {
        "servo": servo_name,
        "ch": SERVO_MAP[servo_name],
        "logical": logical_angle,
        "physical": physical_angle
    }

def move_servos_physical(servo_angles: dict[str, float]):
    """
    複数サーボを物理角で一括制御
    
    Args:
        servo_angles: {servo_name: physical_angle} の形式
    
    Returns:
        {servo_name: {"ch": ch, "logical": logical, "physical": physical}} の形式
    """
    # 存在チェック
    for servo_name in servo_angles.keys():
        if servo_name not in KINEMATICS:
            raise ValueError(f"No kinematics for servo: {servo_name}")
    
    return _apply_physical_multiple(servo_angles)

def move_servos_logical(servo_angles: dict[str, float]):
    """
    複数サーボを論理角で一括制御
    
    Args:
        servo_angles: {servo_name: logical_angle} の形式
    
    Returns:
        {servo_name: {"ch": ch, "logical": logical, "physical": physical}} の形式
    """
    # 論理角→物理角に変換
    physical_angles = {}
    for servo_name, logical_angle in servo_angles.items():
        if servo_name not in KINEMATICS:
            raise ValueError(f"No kinematics for servo: {servo_name}")
        
        kin = KINEMATICS[servo_name]
        physical_angle = kin.logical_to_physical(logical_angle)
        physical_angles[servo_name] = physical_angle
    
    return _apply_physical_multiple(physical_angles)