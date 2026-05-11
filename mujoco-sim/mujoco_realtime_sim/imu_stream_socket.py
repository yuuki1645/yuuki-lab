# type: ignore

"""robot-daemon の ``ImuStreamService`` と同じ Socket.IO イベントで IMU を配信する。"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, Protocol

from flask_socketio import emit

if TYPE_CHECKING:
    from flask_socketio import SocketIO

    from mujoco_realtime_sim.sim_imu_reader import SimImuReader

LOG = logging.getLogger("mujoco_realtime_sim.imu_socket")


class _ImuSampleSource(Protocol):
    enabled: bool

    def sample(self) -> dict[str, Any]: ...

    def get_error_info(self) -> dict[str, str]: ...

    def status(self) -> dict[str, Any]: ...


class MujocoImuStreamService:
    """ストリーム状態・バックグラウンドループ・IMU 用 emit（robot-daemon 互換）。"""

    def __init__(self, socketio: "SocketIO", reader: _ImuSampleSource) -> None:
        self._socketio = socketio
        self._reader = reader
        self._lock = threading.Lock()
        self._rate_hz = 30.0
        self._enabled = False
        self._task_started = False

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            streaming = self._enabled
            rate_hz = self._rate_hz
        return {
            "streaming": streaming,
            "rate_hz": rate_hz,
            "sensor": self._reader.status(),
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
                self._socketio.emit("imu/sample", sample)
            except Exception as e:
                err = self._reader.get_error_info()
                self.emit_error_broadcast(
                    err.get("code") or "IMU_READ_FAILED",
                    "MuJoCo IMU の読み取りに失敗しました。配信を停止します。",
                    str(e),
                )
                with self._lock:
                    self._enabled = False
                self._socketio.emit(
                    "imu/status",
                    {
                        "streaming": False,
                        "rate_hz": rate_hz,
                        "sensor": self._reader.status(),
                    },
                )

            self._socketio.sleep(interval)

    def _ensure_background_task(self) -> None:
        if self._task_started:
            return
        self._task_started = True
        self._socketio.start_background_task(self._stream_loop)

    def register_handlers(self, socketio: "SocketIO") -> None:
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
                        err.get("code") or "IMU_NOT_AVAILABLE",
                        "MuJoCo モデルに IMU センサーがないため、ストリーミングを開始できません。",
                        err.get("message", ""),
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

    def register_connect_handlers(self, socketio: "SocketIO") -> None:
        @socketio.on("connect")
        def ws_connect():
            emit("connection/status", {"status": "connected"})
            emit("imu/status", self.status_payload())

        @socketio.on("disconnect")
        def ws_disconnect():
            LOG.info("Socket.IO client disconnected")


def attach_imu_socketio(
    app: Any,
    simulation: Any,
) -> "SocketIO":
    """Flask アプリに Socket.IO と IMU ストリームを取り付け、インスタンスを返す。"""
    from flask_socketio import SocketIO

    from mujoco_realtime_sim.sim_imu_reader import SimImuReader

    socketio = SocketIO(app, cors_allowed_origins="*")
    reader = SimImuReader(simulation)
    imu = MujocoImuStreamService(socketio, reader)
    imu.register_handlers(socketio)
    imu.register_connect_handlers(socketio)
    app.extensions["socketio"] = socketio
    return socketio
