#!/usr/bin/env python3
# type: ignore
"""Pico W 圧力センサー → Robotics Hub 向けブリッジ。

Pico は HTTP POST（``/api/pressure/sample``）でサンプルを送り、
Hub ブラウザは Socket.IO（``pressure/sample``）でリアルタイム購読する。

既定ポート: **8793**（学習 8791 / Isaac 8792 と衝突しない）。
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import time
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

LOG = logging.getLogger("pressure_telemetry")

DEFAULT_PORT = 8793
DEFAULT_HOST = "0.0.0.0"

# 直近サンプル（ブラウザ接続直後の snapshot 用）
_last_sample: dict[str, Any] | None = None
_sample_count = 0
_last_recv_monotonic = 0.0


def _lan_ipv4() -> str | None:
    """起動ログ用に、外向き経路から推定した LAN IPv4 を返す。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


def _normalize_sample(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Pico からの JSON を正規化する。必須は force_kg。"""
    try:
        force_kg = float(payload.get("force_kg"))
    except (TypeError, ValueError):
        return None

    sample: dict[str, Any] = {
        "force_kg": force_kg,
        "server_ts": time.time(),
    }

    # 任意フィールド（あればそのまま載せる）
    for key, caster in (
        ("voltage_v", float),
        ("rs_ohm", float),
        ("force_pct", float),
        ("adc_pin", int),
        ("device_ts", float),
        ("seq", int),
    ):
        raw = payload.get(key)
        if raw is None:
            continue
        try:
            sample[key] = caster(raw)
        except (TypeError, ValueError):
            pass

    sensor_id = payload.get("sensor_id")
    if isinstance(sensor_id, str) and sensor_id:
        sample["sensor_id"] = sensor_id
    else:
        sample["sensor_id"] = "df9-40"

    return sample


def create_app(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> tuple[Flask, SocketIO]:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "pressure-telemetry-socketio"
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",
    )

    @app.after_request
    def _add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @socketio.on("connect")
    def _on_connect():
        # 接続直後に hello + 直近サンプルを返す（画面の初回表示用）
        emit(
            "pressure/hello",
            {
                "ok": True,
                "server_ts": time.time(),
                "sample_count": _sample_count,
                "stale_sec": (
                    None
                    if _last_recv_monotonic <= 0
                    else max(0.0, time.monotonic() - _last_recv_monotonic)
                ),
            },
        )
        if _last_sample is not None:
            emit("pressure/sample", _last_sample)

    @app.get("/api/pressure/health")
    def health():
        stale = (
            None
            if _last_recv_monotonic <= 0
            else max(0.0, time.monotonic() - _last_recv_monotonic)
        )
        return jsonify(
            {
                "ok": True,
                "sample_count": _sample_count,
                "last_sample": _last_sample,
                "stale_sec": stale,
            }
        )

    @app.route("/api/pressure/sample", methods=["OPTIONS"])
    def sample_options():
        return ("", 204)

    @app.post("/api/pressure/sample")
    def post_sample():
        """Pico W からの圧力サンプル受信。"""
        global _last_sample, _sample_count, _last_recv_monotonic

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "JSON body required"}), 400

        sample = _normalize_sample(payload)
        if sample is None:
            return jsonify({"ok": False, "error": "force_kg must be a number"}), 400

        _last_sample = sample
        _sample_count += 1
        _last_recv_monotonic = time.monotonic()

        # Hub ブラウザへブロードキャスト
        socketio.emit("pressure/sample", sample, namespace="/")
        return jsonify({"ok": True, "sample_count": _sample_count})

    @app.get("/api/pressure/sample")
    def get_sample():
        """デバッグ用: 直近サンプルを返す。"""
        return jsonify({"ok": True, "sample": _last_sample, "sample_count": _sample_count})

    return app, socketio


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Pico pressure → Hub Socket.IO bridge")
    parser.add_argument(
        "--host",
        default=os.environ.get("PRESSURE_TELEMETRY_HOST", DEFAULT_HOST),
        help="bind host (default 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PRESSURE_TELEMETRY_PORT", str(DEFAULT_PORT))),
        help=f"listen port (default {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    app, socketio = create_app(host=args.host, port=args.port)
    lan = _lan_ipv4()
    LOG.info("Pressure telemetry listening on http://%s:%s", args.host, args.port)
    if lan:
        LOG.info("Pico POST target: http://%s:%s/api/pressure/sample", lan, args.port)
        LOG.info("Hub Socket.IO:    http://%s:%s", lan, args.port)

    socketio.run(
        app,
        host=args.host,
        port=args.port,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
