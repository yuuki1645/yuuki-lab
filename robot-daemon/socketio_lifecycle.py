"""接続・切断などアプリ全体の Socket.IO ライフサイクル（IMU 向け）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_socketio import emit

if TYPE_CHECKING:
    from flask_socketio import SocketIO

    from imu_stream_service import ImuStreamService


def register_lifecycle_handlers(socketio: SocketIO, imu: ImuStreamService) -> None:
    @socketio.on("connect")
    def ws_connect():
        emit("connection/status", {"status": "connected"})
        emit("imu/status", imu.status_payload())

    @socketio.on("disconnect")
    def ws_disconnect():
        print("[WS] client disconnected")
