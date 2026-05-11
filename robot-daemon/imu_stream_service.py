# type: ignore

"""IMU の定期サンプリング配信と Socket.IO 上の IMU イベント。"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from flask_socketio import emit

from imu import Mpu6050Reader
from telemetry_csv_bundle import TelemetryCsvBundle

if TYPE_CHECKING:
    from flask_socketio import SocketIO


class ImuStreamService:
    """ストリーム状態・バックグラウンドループ・IMU 用 emit をまとめる。"""

    def __init__(
        self,
        socketio: "SocketIO",
        imu_reader: Mpu6050Reader,
        telemetry_csv: TelemetryCsvBundle | None = None,
    ) -> None:
        self._socketio = socketio
        self._reader = imu_reader
        self._lock = threading.Lock()
        self._rate_hz = 30.0
        self._enabled = False
        self._task_started = False
        self._telemetry = telemetry_csv or TelemetryCsvBundle.from_env()

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            streaming = self._enabled
            rate_hz = self._rate_hz
        return {
            "streaming": streaming,
            "rate_hz": rate_hz,
            "sensor": self._reader.status(),
            "csv_enabled": self._telemetry.enabled,
            "csv_recording": self._telemetry.is_recording(),
            "servo_csv_recording": self._telemetry.servo.is_recording(),
        }

    def emit_error_broadcast(self, code: str, message: str, detail: str | None = None) -> None:
        payload: dict[str, Any] = {
            "ok": False,
            "error_code": code,
            "message": message,
        }
        if detail:
            payload["detail"] = detail
        self._socketio.emit("imu/error", payload)

    def _stream_loop(self) -> None:
        while True:
            with self._lock:
                streaming = self._enabled
                rate_hz = self._rate_hz

            interval = 1.0 / max(1.0, float(rate_hz))
            if not streaming:
                self._socketio.sleep(0.2)
                continue

            try:
                sample = self._reader.sample()
                self._telemetry.imu.record_sample(sample)
                self._socketio.emit("imu/sample", sample)
            except Exception as e:
                err = self._reader.get_error_info()
                self.emit_error_broadcast(
                    err["code"],
                    "MPU6050 の読み取りに失敗しました。配信を停止します。",
                    str(e),
                )
                with self._lock:
                    self._enabled = False
                self._telemetry.end_sessions()
                self._socketio.emit("imu/status", self.status_payload())

            self._socketio.sleep(interval)

    def _ensure_background_task(self) -> None:
        if self._task_started:
            return
        self._task_started = True
        self._socketio.start_background_task(self._stream_loop)

    def register_handlers(self, socketio: "SocketIO") -> None:
        """imu/* の Socket.IO ハンドラを登録する。"""

        @socketio.on("imu/start")
        def ws_imu_start(data):
            try:
                payload = data or {}
                with self._lock:
                    requested = float(payload.get("rate_hz", self._rate_hz))
                    self._rate_hz = max(1.0, min(200.0, requested))
                    self._enabled = True
                if not self._reader.enabled:
                    err = self._reader.get_error_info()
                    with self._lock:
                        self._enabled = False
                    self.emit_error_broadcast(
                        err["code"] or "IMU_NOT_AVAILABLE",
                        "MPU6050 が利用できないため、ストリーミングを開始できません。",
                        err["message"],
                    )
                    emit("imu/status", self.status_payload())
                    return
                self._ensure_background_task()
                emit("imu/status", self.status_payload())
            except Exception as e:
                self.emit_error_broadcast(
                    "IMU_START_FAILED",
                    "IMU ストリーミング開始リクエストの処理に失敗しました。",
                    str(e),
                )

        @socketio.on("imu/stop")
        def ws_imu_stop():
            with self._lock:
                self._enabled = False
            self._telemetry.end_sessions()
            emit("imu/status", self.status_payload())

        @socketio.on("imu/set_rate")
        def ws_imu_set_rate(data):
            try:
                payload = data or {}
                requested_rate = float(payload.get("rate_hz"))
                with self._lock:
                    self._rate_hz = max(1.0, min(200.0, requested_rate))
                emit("imu/status", self.status_payload())
            except Exception as e:
                self.emit_error_broadcast(
                    "IMU_INVALID_RATE",
                    "rate_hz は数値で指定してください（1〜200）。",
                    str(e),
                )

        @socketio.on("imu/status")
        def ws_imu_status():
            emit("imu/status", self.status_payload())

        @socketio.on("imu/log_start")
        def ws_imu_log_start():
            try:
                if not self._telemetry.enabled:
                    emit(
                        "imu/log_status",
                        {"ok": False, "reason": "csv_disabled", "recording": False},
                    )
                    return
                with self._lock:
                    streaming = self._enabled
                if not streaming:
                    emit(
                        "imu/log_status",
                        {"ok": False, "reason": "imu_not_streaming", "recording": False},
                    )
                    emit("imu/status", self.status_payload())
                    return
                self._telemetry.begin_sessions()
                emit(
                    "imu/log_status",
                    {"ok": True, "recording": True},
                )
                emit("imu/status", self.status_payload())
            except Exception as e:
                self.emit_error_broadcast(
                    "IMU_LOG_START_FAILED",
                    "IMU CSV ログ開始の処理に失敗しました。",
                    str(e),
                )
                emit(
                    "imu/log_status",
                    {"ok": False, "reason": "exception", "recording": False},
                )

        @socketio.on("imu/log_stop")
        def ws_imu_log_stop():
            try:
                self._telemetry.end_sessions()
                emit("imu/log_status", {"ok": True, "recording": False})
                emit("imu/status", self.status_payload())
            except Exception as e:
                self.emit_error_broadcast(
                    "IMU_LOG_STOP_FAILED",
                    "IMU CSV ログ停止の処理に失敗しました。",
                    str(e),
                )
