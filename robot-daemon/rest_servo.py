# type: ignore

"""サーボ操作の REST ルート登録（IMU は Socket.IO のまま）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import jsonify, request

from servo_controller import parse_transition_payload

if TYPE_CHECKING:
    from flask import Flask

    from servo_controller import ServoController


def register_servo_rest_routes(app: Flask, servo: ServoController) -> None:
    @app.get("/servos")
    def get_servos():
        return jsonify(servo.list_payload())

    @app.post("/set")
    def set_servo():
        data = request.json or {}
        ch = int(data.get("ch"))
        mode = data.get("mode", "logical")
        angle = float(data.get("angle"))
        result = servo.set_angle(ch, angle, mode)
        return jsonify(
            {
                "status": "ok",
                "logical": result["logical"],
                "physical": result["physical"],
            }
        )

    @app.post("/set_multiple")
    def set_servos_multiple():
        data = request.json or {}
        mode = data.get("mode", "logical")
        angles = data.get("angles", {})
        angles_dict = {int(ch_str): float(angle) for ch_str, angle in angles.items()}
        results = servo.set_angles_batch(angles_dict, mode)
        return jsonify(
            {
                "status": "ok",
                "success_count": len(results["success"]),
                "error_count": len(results["errors"]),
                "results": results,
            }
        )

    @app.post("/transition")
    def transition_servos():
        data = request.json or {}
        mode, angles_dict, duration = parse_transition_payload(data)
        transition_count = servo.start_transition(angles_dict, mode, duration)
        return jsonify(
            {
                "status": "ok",
                "message": f"Transition started for {transition_count} servos over {duration}s",
            }
        )
