#!/usr/bin/env python3
# type: ignore
"""Pico W 圧力センサー → Robotics Hub 向けブリッジ。

Pico は HTTP POST（``/api/pressure/sample``）でサンプルを送り、
Hub ブラウザは Socket.IO（``pressure/sample``）でリアルタイム購読する。

既定ポート: **8793**（学習 8791 / Isaac 8792 と衝突しない）。

配信は HTTP ハンドラから直接 emit せず、最新サンプルをキューに載せて
Socket.IO バックグラウンドタスクから配信する（POST 連打で long-poll が
押し負ける問題を避ける。学習テレメトリと同系統）。
"""

from __future__ import annotations

import argparse
import logging
import os
import queue
import socket
import threading
import time
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

LOG = logging.getLogger("pressure_telemetry")

DEFAULT_PORT = 8793
# 常に全 IF で待ち受ける（127.0.0.1 だけだと LAN の Pico と localhost の Hub が
# 別プロセスに分かれる事故が起きやすい）
DEFAULT_HOST = "0.0.0.0"

# 直近サンプル（ブラウザ接続直後の snapshot / health 用）
_last_sample: dict[str, Any] | None = None
_sample_count = 0
_last_recv_monotonic = 0.0
_state_lock = threading.Lock()

# 最新 1 件だけ残す（POST が速すぎても UI は最新値を追う）
_emit_q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)


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


def _enqueue_emit(sample: dict[str, Any]) -> None:
    """最新サンプルだけを配信キューに載せる（溢れ時は古い方を捨てる）。"""
    try:
        _emit_q.put_nowait(sample)
    except queue.Full:
        try:
            _emit_q.get_nowait()
        except queue.Empty:
            pass
        try:
            _emit_q.put_nowait(sample)
        except queue.Full:
            pass


def create_app() -> tuple[Flask, SocketIO]:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "pressure-telemetry-socketio"
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",
        # POST と Socket.IO ポーリングが同時に捌けるようにする
        ping_timeout=20,
        ping_interval=10,
    )

    @app.after_request
    def _add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @socketio.on("connect")
    def _on_connect():
        with _state_lock:
            count = _sample_count
            last = _last_sample
            recv_m = _last_recv_monotonic
        emit(
            "pressure/hello",
            {
                "ok": True,
                "server_ts": time.time(),
                "sample_count": count,
                "stale_sec": (
                    None if recv_m <= 0 else max(0.0, time.monotonic() - recv_m)
                ),
            },
        )
        if last is not None:
            emit("pressure/sample", last)

    @app.get("/api/pressure/health")
    def health():
        with _state_lock:
            count = _sample_count
            last = _last_sample
            recv_m = _last_recv_monotonic
        stale = None if recv_m <= 0 else max(0.0, time.monotonic() - recv_m)
        return jsonify(
            {
                "ok": True,
                "sample_count": count,
                "last_sample": last,
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

        with _state_lock:
            _last_sample = sample
            _sample_count += 1
            _last_recv_monotonic = time.monotonic()
            count = _sample_count

        # 直接 emit せず、Socket.IO 側タスクへ渡す
        _enqueue_emit(sample)
        return jsonify({"ok": True, "sample_count": count})

    @app.get("/api/pressure/sample")
    def get_sample():
        with _state_lock:
            last = _last_sample
            count = _sample_count
        return jsonify({"ok": True, "sample": last, "sample_count": count})

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
        help="bind host (default 0.0.0.0 — do not use 127.0.0.1 alone)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PRESSURE_TELEMETRY_PORT", str(DEFAULT_PORT))),
        help=f"listen port (default {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    if args.host in ("127.0.0.1", "localhost"):
        LOG.warning(
            "host=%s binds loopback only. Pico on LAN cannot reach this process, "
            "and a second 0.0.0.0 listener may split traffic. Prefer 0.0.0.0.",
            args.host,
        )

    app, socketio = create_app()

    def _drain_loop() -> None:
        """キューから取り出してブラウザへ broadcast。"""
        while True:
            try:
                sample = _emit_q.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                socketio.emit("pressure/sample", sample, namespace="/")
            except Exception:
                LOG.exception("failed to emit pressure/sample")

    # run 直前に開始（学習テレメトリと同じく Socket.IO タスクとして配信）
    socketio.start_background_task(_drain_loop)

    lan = _lan_ipv4()
    LOG.info("Pressure telemetry listening on http://%s:%s", args.host, args.port)
    if lan:
        LOG.info("Pico POST target: http://%s:%s/api/pressure/sample", lan, args.port)
        LOG.info("Hub Socket.IO:    http://%s:%s  (or http://127.0.0.1:%s)", lan, args.port, args.port)

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
