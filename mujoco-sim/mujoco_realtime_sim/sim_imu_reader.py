# type: ignore

"""MuJoCo の IMU 系センサーから、robot-daemon の MPU6050 と同形のサンプル辞書を生成する。"""

from __future__ import annotations

import math
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mujoco_realtime_sim.core import Simulation

_G = 9.80665


class SimImuReader:
    """``imu_acc`` / ``imu_gyro``（MJCF 既定名）を読み、補完フィルタで pitch/roll/yaw を推定。"""

    def __init__(
        self,
        simulation: "Simulation",
        acc_name: str = "imu_acc",
        gyro_name: str = "imu_gyro",
        alpha: float = 0.98,
    ) -> None:
        self._sim = simulation
        self._acc_name = acc_name
        self._gyro_name = gyro_name
        self._alpha = alpha
        self._lock = threading.Lock()
        self._pitch = 0.0
        self._roll = 0.0
        self._yaw = 0.0
        self._last_perf = 0.0
        self._missing: str | None = None
        self._check_sensors()

    def _check_sensors(self) -> None:
        model = self._sim.model
        import mujoco

        if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, self._acc_name) < 0:
            self._missing = f"accelerometer sensor {self._acc_name!r} not in model"
            return
        if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, self._gyro_name) < 0:
            self._missing = f"gyro sensor {self._gyro_name!r} not in model"
            return
        self._missing = None

    @property
    def enabled(self) -> bool:
        return self._missing is None

    def get_error_info(self) -> dict[str, str]:
        if self._missing:
            return {"code": "IMU_SENSORS_MISSING", "message": self._missing}
        return {"code": "", "message": ""}

    def status(self) -> dict[str, Any]:
        err = self.get_error_info()
        return {
            "enabled": self.enabled,
            "mock_mode": False,
            "error": err["message"] if not self.enabled else "",
            "error_code": err["code"] if not self.enabled else "",
            "source": "mujoco_sim",
        }

    def sample(self) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(self._missing or "IMU sensors not available")

        perf_now = time.perf_counter()
        with self._lock:
            prev_perf = self._last_perf
            self._last_perf = perf_now
        dt = max(0.0, perf_now - prev_perf) if prev_perf > 0 else (1.0 / 60.0)

        acc = self._sim.read_sensor(self._acc_name)
        gyro = self._sim.read_sensor(self._gyro_name)
        if acc is None or len(acc) < 3 or gyro is None or len(gyro) < 3:
            raise RuntimeError("failed to read imu_acc / imu_gyro")

        ax_m, ay_m, az_m = acc[0], acc[1], acc[2]
        gx_rad, gy_rad, gz_rad = gyro[0], gyro[1], gyro[2]

        ax_g = ax_m / _G
        ay_g = ay_m / _G
        az_g = az_m / _G
        gx_deg = math.degrees(gx_rad)
        gy_deg = math.degrees(gy_rad)
        gz_deg = math.degrees(gz_rad)

        acc_pitch = math.degrees(math.atan2(ay_m, math.sqrt(ax_m * ax_m + az_m * az_m)))
        acc_roll = math.degrees(math.atan2(-ax_m, math.sqrt(ay_m * ay_m + az_m * az_m)))

        with self._lock:
            self._pitch = (
                self._alpha * (self._pitch + gx_deg * dt)
                + (1.0 - self._alpha) * acc_pitch
            )
            self._roll = (
                self._alpha * (self._roll + gy_deg * dt)
                + (1.0 - self._alpha) * acc_roll
            )
            self._yaw += gz_deg * dt
            pitch = self._pitch
            roll = self._roll
            yaw = self._yaw

        return {
            "timestamp": perf_now,
            "mock": False,
            "accel": {"x": ax_g, "y": ay_g, "z": az_g},
            "gyro": {"x": gx_deg, "y": gy_deg, "z": gz_deg},
            "angle": {"pitch": pitch, "roll": roll, "yaw": yaw},
        }
