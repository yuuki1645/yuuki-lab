#!/usr/bin/env python3
"""
atom-rt の lab_debug.py 用 iPad / robotics-hub 中継（Socket.IO）。

ATOM の USB は触らない。Tk スレッドから publish し、iPad からの操作は
コールバックで Tk に戻す。既定ポート 8794（学習 8791 / Isaac 8792 / 圧力 8793）。
"""

from __future__ import annotations

import logging
import queue
import socket
import threading
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from m5_record_store import M5RecordStore

LOG = logging.getLogger("m5_hub_bridge")

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8794

# イベント名。Hub 側 useM5TelemetryStream と揃える
EVT_HELLO = "m5/hello"
EVT_STATUS = "m5/status"
EVT_FRAME = "m5/frame"
EVT_CONTROL = "m5/control"
EVT_SCAN = "m5/scan"
EVT_PROFILE = "m5/profile"
EVT_EVENTS = "m5/events"
EVT_CAL = "m5/cal"
EVT_RECORD = "m5/record"
CMD_EVENT = "m5/cmd"


def lan_ipv4() -> str | None:
    """起動ログ用の LAN IPv4。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


class M5HubBridge:
    """Flask-SocketIO を裏スレッドで動かす。無いときは enabled=False。"""

    def __init__(
        self,
        on_command: Callable[[dict[str, Any]], None],
        on_clients_changed: Callable[[int], None],
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        store: "M5RecordStore | None" = None,
    ) -> None:
        self.on_command = on_command
        self.on_clients_changed = on_clients_changed
        self.host = host
        self.port = port
        self.store = store
        self.enabled = False
        self.client_count = 0
        self._lock = threading.Lock()
        self._emit_q: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=32)
        self._snapshot: Callable[[], dict[str, Any]] | None = None
        self._thread: threading.Thread | None = None
        self._socketio = None
        self._app = None

        try:
            from flask import Flask, jsonify, request
            from flask_cors import CORS
            from flask_socketio import SocketIO, emit
        except ImportError:
            LOG.warning(
                "flask / flask-socketio が無いので iPad ブリッジは無効。"
                " pip install -r tools/requirements.txt"
            )
            return

        app = Flask("m5_hub_bridge")
        CORS(app)
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode="threading",
            logger=False,
            engineio_logger=False,
        )
        self._app = app
        self._socketio = socketio
        self.enabled = True

        @app.get("/api/m5/health")
        def health():
            with self._lock:
                n = self.client_count
            body = {"ok": True, "clients": n, "port": self.port}
            if self.store is not None:
                body["record"] = self.store.status()
            return jsonify(body)

        # ----- 本記録 API（正本は PC ディスク。Hub はここ経由） -----
        @app.get("/api/m5/record/status")
        def record_status():
            if self.store is None:
                return jsonify({"ok": False, "error": "store missing"}), 500
            body = self.store.status()
            body["ok"] = True
            return jsonify(body)

        @app.post("/api/m5/record/start")
        def record_start():
            body = request.get_json(silent=True) or {}
            self.on_command(
                {
                    "op": "record_start",
                    "name": body.get("name") or "",
                    "notes": body.get("notes") or "",
                }
            )
            return jsonify({"ok": True, "accepted": True})

        @app.post("/api/m5/record/stop")
        def record_stop():
            self.on_command({"op": "record_stop"})
            return jsonify({"ok": True, "accepted": True})

        @app.get("/api/m5/recordings")
        def recordings_list():
            if self.store is None:
                return jsonify({"ok": False, "error": "store missing"}), 500
            return jsonify({"ok": True, "recordings": self.store.list_recordings()})

        @app.get("/api/m5/recordings/<rec_id>")
        def recording_get(rec_id: str):
            if self.store is None:
                return jsonify({"ok": False, "error": "store missing"}), 500
            row = self.store.get_recording(rec_id)
            if row is None:
                return jsonify({"ok": False, "error": "not found"}), 404
            row["ok"] = True
            return jsonify(row)

        @app.get("/api/m5/recordings/<rec_id>/frames")
        def recording_frames(rec_id: str):
            if self.store is None:
                return jsonify({"ok": False, "error": "store missing"}), 500
            if self.store.get_recording(rec_id) is None:
                return jsonify({"ok": False, "error": "not found"}), 404
            try:
                offset = int(request.args.get("offset", 0))
                limit = int(request.args.get("limit", 4000))
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "bad query"}), 400
            frames, total = self.store.read_frames(rec_id, offset, limit)
            return jsonify(
                {
                    "ok": True,
                    "id": rec_id,
                    "offset": max(0, offset),
                    "total": total,
                    "frames": frames,
                }
            )

        @app.patch("/api/m5/recordings/<rec_id>")
        def recording_patch(rec_id: str):
            if self.store is None:
                return jsonify({"ok": False, "error": "store missing"}), 500
            body = request.get_json(silent=True) or {}
            name = body["name"] if "name" in body else None
            notes = body["notes"] if "notes" in body else None
            camera = body["camera"] if "camera" in body else None
            if name is not None and not isinstance(name, str):
                return jsonify({"ok": False, "error": "name"}), 400
            if notes is not None and not isinstance(notes, str):
                return jsonify({"ok": False, "error": "notes"}), 400
            if camera is not None and not isinstance(camera, dict):
                return jsonify({"ok": False, "error": "camera"}), 400
            row = self.store.patch(rec_id, name=name, notes=notes, camera=camera)
            if row is None:
                return jsonify({"ok": False, "error": "not found"}), 404
            row["ok"] = True
            return jsonify(row)

        @app.delete("/api/m5/recordings/<rec_id>")
        def recording_delete(rec_id: str):
            if self.store is None:
                return jsonify({"ok": False, "error": "store missing"}), 500
            ok, err = self.store.delete(rec_id)
            if not ok:
                return jsonify({"ok": False, "error": err}), 400
            return jsonify({"ok": True, "id": rec_id})

        @socketio.on("connect")
        def _on_connect():
            with self._lock:
                self.client_count += 1
                n = self.client_count
            self._notify_clients(n)
            snap = self._snapshot() if self._snapshot else {}
            emit(EVT_HELLO, snap)

        @socketio.on("disconnect")
        def _on_disconnect():
            with self._lock:
                self.client_count = max(0, self.client_count - 1)
                n = self.client_count
            self._notify_clients(n)

        @socketio.on(CMD_EVENT)
        def _on_cmd(payload: Any):
            if not isinstance(payload, dict):
                return
            try:
                self.on_command(payload)
            except Exception:
                LOG.exception("m5/cmd handler")

    def set_snapshot(self, fn: Callable[[], dict[str, Any]]) -> None:
        """接続直後に送るスナップショット関数。"""
        self._snapshot = fn

    def start(self) -> None:
        if not self.enabled or self._socketio is None or self._app is None:
            return
        socketio = self._socketio
        app = self._app

        def _drain() -> None:
            while True:
                try:
                    name, payload = self._emit_q.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    socketio.emit(name, payload, namespace="/")
                except Exception:
                    LOG.exception("emit %s", name)

        def _run() -> None:
            socketio.start_background_task(_drain)
            lan = lan_ipv4()
            LOG.info("M5 hub bridge http://%s:%s", self.host, self.port)
            if lan:
                LOG.info("iPad: Hub を開き 実機テレメトリ（M5）  http://%s:5173/m5-telemetry", lan)
            socketio.run(
                app,
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                allow_unsafe_werkzeug=True,
            )

        self._thread = threading.Thread(target=_run, name="m5-hub-bridge", daemon=True)
        self._thread.start()

    def publish(self, event: str, payload: Any) -> None:
        """最新を優先してキューに載せる。満杯なら古い frame を捨てる。"""
        if not self.enabled:
            return
        with self._lock:
            if self.client_count <= 0:
                return
        try:
            self._emit_q.put_nowait((event, payload))
        except queue.Full:
            try:
                _ = self._emit_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._emit_q.put_nowait((event, payload))
            except queue.Full:
                pass

    def _notify_clients(self, n: int) -> None:
        try:
            self.on_clients_changed(n)
        except Exception:
            LOG.exception("on_clients_changed")
