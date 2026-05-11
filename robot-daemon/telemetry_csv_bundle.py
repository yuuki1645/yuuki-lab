# type: ignore

"""IMU CSV とサーボ指令 CSV を同一セッションで開始・停止する。"""

from __future__ import annotations

from imu_csv_log import ImuCsvLog, imu_csv_log_from_env
from servo_csv_log import ServoCsvLog, servo_csv_log_from_env


class TelemetryCsvBundle:
    def __init__(self, imu: ImuCsvLog, servo: ServoCsvLog) -> None:
        self.imu = imu
        self.servo = servo

    @classmethod
    def from_env(cls) -> TelemetryCsvBundle:
        return cls(imu_csv_log_from_env(), servo_csv_log_from_env())

    @property
    def enabled(self) -> bool:
        return self.imu.enabled

    def is_recording(self) -> bool:
        return self.imu.is_recording()

    def begin_sessions(self) -> None:
        self.imu.begin_session()
        self.servo.begin_session()

    def end_sessions(self) -> None:
        self.imu.end_session()
        self.servo.end_session()
