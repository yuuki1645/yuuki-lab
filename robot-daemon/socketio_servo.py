# type: ignore

"""サーボ関連の Socket.IO ハンドラ登録。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_socketio import emit

from servo_controller import parse_transition_payload

if TYPE_CHECKING:
    from flask_socketio import SocketIO

    from servo_controller import ServoController


def register_servo_handlers(socketio: SocketIO, servo: ServoController) -> None:
    @socketio.on("servo/list")
    def ws_servo_list(_data=None):
        try:
            emit("servo/list", servo.list_payload())
        except Exception as e:
            emit("error", {"status": "error", "message": str(e)})

    @socketio.on("servo/set")
    def ws_set_servo(data):
        try:
            ch = int(data.get("ch"))
            mode = data.get("mode", "logical")
            angle = float(data.get("angle"))
            result = servo.set_angle(ch, angle, mode)
            emit("servo/result", {"status": "ok", "result": result})
        except Exception as e:
            emit("error", {"status": "error", "message": str(e)})

    @socketio.on("servo/set_multiple")
    def ws_set_multiple(data):
        try:
            mode = data.get("mode", "logical")
            angles = data.get("angles", {})
            angles_dict = {int(ch_str): float(angle) for ch_str, angle in angles.items()}
            results = servo.set_angles_batch(angles_dict, mode)
            emit("servo/result_multiple", {"status": "ok", "results": results})
        except Exception as e:
            emit("error", {"status": "error", "message": str(e)})

    @socketio.on("servo/transition")
    def ws_transition(data):
        try:
            mode, angles_dict, duration = parse_transition_payload(data or {})
            transition_count = servo.start_transition(angles_dict, mode, duration)
            emit(
                "servo/transition_started",
                {
                    "status": "ok",
                    "message": f"Transition started for {transition_count} servos over {duration}s",
                },
            )
        except Exception as e:
            emit("error", {"status": "error", "message": str(e)})
