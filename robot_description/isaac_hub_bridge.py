#!/usr/bin/env python3
"""robotics-hub と Isaac 再生スクリプトのあいだに立つ橋。

Hub とは実機と同じ Socket.IO イベント（m5/frame, m5/cmd, m5/control）。
ポートは 8795。実機の lab_debug.py（8794）とは同時に使わない。

Isaac とは 127.0.0.1:8796 の TCP で JSON を 1 行ずつやり取りする。
度とラジアンの変換はここだけで行う。Isaac 側に flask は入れない。

起動（Hub 用の Python。flask-socketio が入っているもの）:
    python robot_description/isaac_hub_bridge.py
"""

from __future__ import annotations

import json
import logging
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

# プロジェクトルートから `python robot_description/isaac_hub_bridge.py` しても読めるようにする。
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from flask import Flask
from flask_socketio import SocketIO, emit

from hub_link import (
    HUB_PORT,
    ISAAC_TCP_HOST,
    ISAAC_TCP_PORT,
    JOINT_COUNT,
    NEUTRAL_DEG,
    deg_to_rad,
    joint_names,
    rad_to_deg,
)

LOG = logging.getLogger("isaac_hub_bridge")

# Hub が既に購読しているイベント名。画面側は実機と同じコードで描く。
EVT_HELLO = "m5/hello"
EVT_FRAME = "m5/frame"
EVT_CONTROL = "m5/control"
EVT_STATUS = "m5/status"
EVT_CMD = "m5/cmd"


class Bridge:
    """指令（度）と計測（ラジアン）を保持し、両側へ配る。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # 画面の指令。PWM が OFF の関節は Isaac へ目標を出さない。
        self.cmd_deg = [NEUTRAL_DEG] * JOINT_COUNT
        self.out = [False] * JOINT_COUNT
        # Isaac から届いた関節角（rad）。未接続のあいだは None。
        self.meas_rad: list[float | None] = [None] * JOINT_COUNT
        self.sim_time = 0.0
        self.isaac_connected = False
        self.seq = 0
        self._isaac_send: Any = None
        self._socketio: SocketIO | None = None

    def set_emitters(self, socketio: SocketIO, isaac_send) -> None:
        self._socketio = socketio
        self._isaac_send = isaac_send

    def on_isaac_line(self, line: str) -> None:
        """Isaac からの 1 行。関節角を覚えて Hub へフレームを出す。"""
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            LOG.warning("Isaac からの JSON が壊れています: %s", line[:120])
            return
        if msg.get("op") != "joints":
            return
        rads = msg.get("rad")
        if not isinstance(rads, list) or len(rads) != JOINT_COUNT:
            LOG.warning("関節数は %s である必要があります", JOINT_COUNT)
            return
        with self._lock:
            self.meas_rad = [float(v) for v in rads]
            self.sim_time = float(msg.get("sim_time") or 0.0)
            self.isaac_connected = True
            self.seq += 1
            frame = self._frame_locked()
            control = self._control_locked()
            status = self._status_locked()
        self._emit(EVT_FRAME, frame)
        self._emit(EVT_CONTROL, control)
        self._emit(EVT_STATUS, status)

    def on_hub_cmd(self, payload: dict) -> None:
        """画面の m5/cmd。joint / out / hold だけ Isaac に関係する。"""
        op = payload.get("op")
        with self._lock:
            if op == "joint":
                ch = int(payload.get("ch", -1))
                deg = float(payload.get("deg", NEUTRAL_DEG))
                if 0 <= ch < JOINT_COUNT:
                    self.cmd_deg[ch] = deg
            elif op == "out":
                ch = int(payload.get("ch", -1))
                if 0 <= ch < JOINT_COUNT:
                    self.out[ch] = bool(payload.get("on"))
            elif op == "hold":
                # 全停止。目標は直立に戻し、出力を切る。
                self.cmd_deg = [NEUTRAL_DEG] * JOINT_COUNT
                self.out = [False] * JOINT_COUNT
            else:
                # スキャンや NVS など実機専用の操作。Isaac では何もしない。
                return
            control = self._control_locked()
            targets = self._targets_locked()
        self._emit(EVT_CONTROL, control)
        if self._isaac_send is not None:
            self._isaac_send(targets)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status": self._status_locked(),
                "control": self._control_locked(),
                "frame": self._frame_locked(),
            }

    def mark_isaac(self, connected: bool) -> None:
        with self._lock:
            self.isaac_connected = connected
            if not connected:
                self.meas_rad = [None] * JOINT_COUNT
            status = self._status_locked()
        self._emit(EVT_STATUS, status)
        if connected and self._isaac_send is not None:
            with self._lock:
                targets = self._targets_locked()
            self._isaac_send(targets)

    def _targets_locked(self) -> dict:
        """PWM ON の関節だけ目標ラジアンを載せる。OFF は null（その場で保持）。"""
        rad: list[float | None] = []
        for deg, enabled in zip(self.cmd_deg, self.out):
            rad.append(deg_to_rad(deg) if enabled else None)
        return {"op": "targets", "names": joint_names(), "rad": rad}

    def _control_locked(self) -> dict:
        return {
            "out": list(self.out),
            "cmd": list(self.cmd_deg),
            "rand": [False] * JOINT_COUNT,
            "amp_limit": 0,
            "auto_scan": False,
            "rand_min": 100,
            "rand_max": 170,
            "rand_hold_min": 0,
            "rand_hold_max": 0,
            "rand_jump": 0,
        }

    def _frame_locked(self) -> dict:
        corr: list[float | None] = []
        for rad in self.meas_rad:
            corr.append(None if rad is None else rad_to_deg(rad))
        cmd: list[float | None] = list(self.cmd_deg)
        # 電圧・電流はシミュに無い。null のまま画面側が非アクティブ表示にする。
        empty: list[float | None] = [None] * JOINT_COUNT
        mask = 0
        for i, on in enumerate(self.out):
            if on:
                mask |= 1 << i
        return {
            "t": time.time(),
            "seq": self.seq,
            "period_us": 50_000,
            "loop_us": 0,
            "sense_us": 0,
            "jitter_us": 0,
            "overrun": False,
            "cmd": cmd,
            "raw": list(corr),
            "unwrap": list(corr),
            "corr": corr,
            "as_ok": [v is not None for v in corr],
            "mag": [0] * JOINT_COUNT,
            "agc": [0] * JOINT_COUNT,
            "volt": list(empty),
            "amp": list(empty),
            "watt": list(empty),
            "ina_ok": [False] * JOINT_COUNT,
            "i2c_err": 0,
            "servo_ok": self.isaac_connected,
            "mode": "isaac",
            "out_mask": mask,
            "foot": None,
            "sim_time": self.sim_time,
        }

    def _status_locked(self) -> dict:
        return {
            "ipad_clients": 0,
            "pc_locked": False,
            "connected": self.isaac_connected,
            "port": "isaac",
            "name": "Isaac Sim",
            "hello": "電圧・電流は未計測。135° が直立です。",
            "mode": "isaac",
            "bridge_port": HUB_PORT,
        }

    def _emit(self, event: str, payload: dict) -> None:
        if self._socketio is None:
            return
        try:
            self._socketio.emit(event, payload, namespace="/")
        except Exception:
            LOG.exception("emit %s", event)


class IsaacTcp(threading.Thread):
    """127.0.0.1 で Isaac 再生スクリプトを 1 本待つ。"""

    def __init__(self, bridge: Bridge) -> None:
        super().__init__(daemon=True, name="isaac-tcp")
        self.bridge = bridge
        self._stop = threading.Event()
        self._client: socket.socket | None = None
        self._buf = b""
        self._send_lock = threading.Lock()

    def send(self, payload: dict) -> None:
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        with self._send_lock:
            client = self._client
            if client is None:
                return
            try:
                client.sendall(data)
            except OSError:
                LOG.warning("Isaac への送信に失敗しました")
                self._drop_client()

    def run(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ISAAC_TCP_HOST, ISAAC_TCP_PORT))
        server.listen(1)
        server.settimeout(0.4)
        LOG.info("Isaac TCP %s:%s", ISAAC_TCP_HOST, ISAAC_TCP_PORT)
        while not self._stop.is_set():
            if self._client is None:
                try:
                    client, _addr = server.accept()
                except socket.timeout:
                    continue
                client.settimeout(0.2)
                with self._send_lock:
                    self._client = client
                self._buf = b""
                LOG.info("Isaac 再生スクリプトが接続しました")
                self.bridge.mark_isaac(True)
            else:
                self._read_some()
        server.close()
        self._drop_client()

    def _read_some(self) -> None:
        client = self._client
        if client is None:
            return
        try:
            chunk = client.recv(65536)
        except socket.timeout:
            return
        except OSError:
            self._drop_client()
            return
        if not chunk:
            self._drop_client()
            return
        self._buf += chunk
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                self.bridge.on_isaac_line(text)

    def _drop_client(self) -> None:
        with self._send_lock:
            client = self._client
            self._client = None
        if client is not None:
            try:
                client.close()
            except OSError:
                pass
        self.bridge.mark_isaac(False)
        LOG.info("Isaac 再生スクリプトが切れました")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bridge = Bridge()
    tcp = IsaacTcp(bridge)
    tcp.start()

    app = Flask("isaac_hub_bridge")
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
    bridge.set_emitters(socketio, tcp.send)

    @socketio.on("connect")
    def _on_connect():
        # emit は接続してきたクライアントだけに返す。全体へ放送すると他の画面の状態が混ざる。
        snap = bridge.snapshot()
        emit(EVT_HELLO, snap)
        emit(EVT_STATUS, snap["status"])
        emit(EVT_CONTROL, snap["control"])
        emit(EVT_FRAME, snap["frame"])

    @socketio.on(EVT_CMD)
    def _on_cmd(payload: Any):
        if isinstance(payload, dict):
            bridge.on_hub_cmd(payload)

    LOG.info("Hub Socket.IO http://0.0.0.0:%s  （実機テレメトリの画面が接続します）", HUB_PORT)
    socketio.run(app, host="0.0.0.0", port=HUB_PORT, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
