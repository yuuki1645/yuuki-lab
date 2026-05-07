import math
import os
import random
import threading
import time
from typing import Any


class Mpu6050Reader:
    """MPU6050 を読み取り、補完フィルタで姿勢角を推定する。"""

    def __init__(self, bus_id: int = 1, address: int = 0x68):
        self.bus_id = bus_id
        self.address = address
        self.bus = None
        self.enabled = False
        self.mock_mode = False
        self.last_error = ""
        self.last_error_code = ""

        self._lock = threading.Lock()
        self._pitch = 0.0
        self._roll = 0.0
        self._yaw = 0.0
        self._last_perf = 0.0
        self._alpha = 0.98
        self._mock_ax = 0.0
        self._mock_ay = 0.0
        self._mock_az = 1.0
        self._mock_gx = 0.0
        self._mock_gy = 0.0
        self._mock_gz = 0.0
        self._mock_t = 0.0

        try:
            import smbus2

            self.bus = smbus2.SMBus(self.bus_id)
            # PWR_MGMT_1=0 -> スリープ解除
            self.bus.write_byte_data(self.address, 0x6B, 0)
            self.enabled = True
        except Exception as e:
            self.enabled = False
            self.last_error = str(e)
            self.last_error_code = "IMU_INIT_FAILED"
            self._try_enable_mock_mode()

        # 明示指定があれば実機初期化成功時でもモックを優先
        if self._env_truthy("IMU_MOCK"):
            self._enable_mock_mode("IMU_MOCK is enabled by environment")

    def _env_truthy(self, key: str) -> bool:
        val = os.getenv(key, "")
        return val.lower() in ("1", "true", "yes", "on")

    def _try_enable_mock_mode(self):
        # Windows 開発環境では、実機未接続でもUI開発を進められるよう自動でモック化
        if os.name == "nt" or self._env_truthy("IMU_MOCK"):
            self._enable_mock_mode(
                "MPU6050 unavailable. Running in mock mode for development."
            )

    def _enable_mock_mode(self, reason: str):
        self.mock_mode = True
        self.enabled = True
        self.last_error = reason
        self.last_error_code = "IMU_MOCK_MODE"

    def _read_word(self, reg: int) -> int:
        if self.bus is None:
            raise RuntimeError("I2C bus is not initialized")
        high = self.bus.read_byte_data(self.address, reg)
        low = self.bus.read_byte_data(self.address, reg + 1)
        val = (high << 8) + low
        if val >= 0x8000:
            val = -((65535 - val) + 1)
        return val

    def sample(self) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(self.last_error or "MPU6050 is not enabled")

        perf_now = time.perf_counter()
        with self._lock:
            prev_perf = self._last_perf
            self._last_perf = perf_now
        dt = max(0.0, perf_now - prev_perf) if prev_perf > 0 else 0.0

        if self.mock_mode:
            ax, ay, az, gx, gy, gz = self._mock_sample(dt)
        else:
            try:
                ax = self._read_word(0x3B) / 16384.0
                ay = self._read_word(0x3D) / 16384.0
                az = self._read_word(0x3F) / 16384.0

                gx = self._read_word(0x43) / 131.0
                gy = self._read_word(0x45) / 131.0
                gz = self._read_word(0x47) / 131.0
            except Exception as e:
                self.last_error = str(e)
                self.last_error_code = "IMU_READ_FAILED"
                raise

        acc_pitch = math.degrees(math.atan2(ay, math.sqrt(ax * ax + az * az)))
        acc_roll = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))

        with self._lock:
            self._pitch = self._alpha * (self._pitch + gx * dt) + (1 - self._alpha) * acc_pitch
            self._roll = self._alpha * (self._roll + gy * dt) + (1 - self._alpha) * acc_roll
            self._yaw += gz * dt
            pitch = self._pitch
            roll = self._roll
            yaw = self._yaw

        return {
            "timestamp": perf_now,
            "mock": self.mock_mode,
            "accel": {"x": ax, "y": ay, "z": az},
            "gyro": {"x": gx, "y": gy, "z": gz},
            "angle": {"pitch": pitch, "roll": roll, "yaw": yaw},
        }

    def _mock_sample(self, dt: float) -> tuple[float, float, float, float, float, float]:
        # UI確認用: なめらかに変化する疑似センサー値
        self._mock_t += max(dt, 1.0 / 60.0)
        t = self._mock_t

        self._mock_ax = 0.20 * math.sin(t * 0.9) + random.uniform(-0.03, 0.03)
        self._mock_ay = 0.25 * math.sin(t * 1.1 + 0.8) + random.uniform(-0.03, 0.03)
        self._mock_az = 1.0 + 0.05 * math.sin(t * 0.6) + random.uniform(-0.02, 0.02)

        self._mock_gx = 15.0 * math.sin(t * 0.7) + random.uniform(-1.5, 1.5)
        self._mock_gy = 12.0 * math.sin(t * 0.8 + 0.5) + random.uniform(-1.5, 1.5)
        self._mock_gz = 8.0 * math.sin(t * 0.4 + 1.2) + random.uniform(-1.0, 1.0)

        return (
            self._mock_ax,
            self._mock_ay,
            self._mock_az,
            self._mock_gx,
            self._mock_gy,
            self._mock_gz,
        )

    def get_error_info(self) -> dict[str, str]:
        code = self.last_error_code or "IMU_UNKNOWN_ERROR"
        message = self.last_error or "Unknown IMU error"
        return {"code": code, "message": message}

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mock_mode": self.mock_mode,
            "error": self.last_error,
            "error_code": self.last_error_code,
            "bus_id": self.bus_id,
            "address": self.address,
        }
