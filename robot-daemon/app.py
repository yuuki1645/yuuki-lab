# type: ignore

import argparse
import logging

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from imu import Mpu6050Reader
from imu_stream_service import ImuStreamService
from rest_servo import register_servo_rest_routes
from servo_controller import ServoController
from state_manager import StateManager
import socketio_lifecycle
from telemetry_csv_bundle import TelemetryCsvBundle

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

state_manager = StateManager(state_path="./state.json")
imu_reader = Mpu6050Reader()

servo_controller = ServoController(state_manager)
telemetry_csv = TelemetryCsvBundle.from_env()
imu_stream = ImuStreamService(socketio, imu_reader, telemetry_csv=telemetry_csv)

register_servo_rest_routes(app, servo_controller, servo_csv_log=telemetry_csv.servo)
socketio_lifecycle.register_lifecycle_handlers(socketio, imu_stream)
imu_stream.register_handlers(socketio)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Servo daemon（サーボ: REST / IMU: Socket.IO）"
    )
    parser.add_argument(
        "--access-log",
        action="store_true",
        help="Werkzeug の HTTP アクセスログを出す。デフォルトはオフ。",
    )
    args = parser.parse_args()
    if not args.access_log:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
