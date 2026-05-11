# type: ignore

"""学習プロセス内で動かす Flask-SocketIO サーバ（キュー経由で emit）。"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from flask import Flask, jsonify, request


class RlTelemetryServer:
    """
    別スレッドで ``socketio.run`` し、学習スレッドは ``publish_*`` でキューに積む。
    バックグラウンドタスクが ``rl_telemetry/*`` をクライアントへ送る。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8791,
        set_step_wall_sleep_sec: Callable[[float], None] | None = None,
        get_step_wall_sleep_sec: Callable[[], float] | None = None,
    ) -> None:
        self.host = host
        self.port = int(port)
        self._q: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue(maxsize=512)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._set_step_wall_sleep_sec = set_step_wall_sleep_sec
        self._get_step_wall_sleep_sec = get_step_wall_sleep_sec

        self.app = Flask(__name__)
        self.app.config["SECRET_KEY"] = "rl-telemetry"

        @self.app.after_request
        def _add_cors_headers(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            return response

        from flask_socketio import SocketIO

        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            async_mode="threading",
        )

        @self.socketio.on("connect")
        def _on_connect() -> None:
            from flask_socketio import emit

            emit("rl_telemetry/hello", {"ok": True, "server_ts": time.time()})

        @self.app.get("/api/rl_telemetry/config")
        def _get_config():
            current = None
            if callable(self._get_step_wall_sleep_sec):
                try:
                    current = float(self._get_step_wall_sleep_sec())
                except Exception:
                    current = None
            return jsonify({"step_wall_sleep_sec": current})

        @self.app.post("/api/rl_telemetry/config")
        def _set_config():
            if not callable(self._set_step_wall_sleep_sec):
                return jsonify({"error": "step_wall_sleep setter is not available"}), 400
            payload = request.get_json(silent=True) or {}
            try:
                value = max(0.0, float(payload.get("step_wall_sleep_sec", 0.0)))
            except Exception:
                return jsonify({"error": "step_wall_sleep_sec must be a number"}), 400
            self._set_step_wall_sleep_sec(value)
            return jsonify({"status": "ok", "step_wall_sleep_sec": value})

        @self.app.route("/api/rl_telemetry/config", methods=["OPTIONS"])
        def _config_options():
            return ("", 204)

    def _drain_loop(self) -> None:
        while not self._stop.is_set():
            try:
                kind, payload = self._q.get(timeout=0.1)
            except queue.Empty:
                continue
            self.socketio.emit(f"rl_telemetry/{kind}", payload, namespace="/")

    def _run_blocking(self) -> None:
        self.socketio.start_background_task(self._drain_loop)
        self.socketio.run(
            self.app,
            host=self.host,
            port=self.port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_blocking, daemon=True)
        self._thread.start()
        time.sleep(0.2)

    def stop(self) -> None:
        self._stop.set()
        # socketio.run はプロセス終了までブロックしがちなので、学習終了時はスレッド放置で可

    def publish_step(self, payload: dict[str, Any]) -> None:
        try:
            self._q.put_nowait(("step", payload))
        except queue.Full:
            pass

    def publish_reset(self, payload: dict[str, Any]) -> None:
        try:
            self._q.put_nowait(("reset", payload))
        except queue.Full:
            pass
