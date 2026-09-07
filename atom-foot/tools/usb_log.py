#!/usr/bin/env python3
"""
足裏マスターの USB フレームをターミナルに出す CLI。

GUI を開いているときは COM を同時に使えないので、閉じてから起動する。

  python tools/usb_log.py
  python tools/usb_log.py COM11

キーボード: ping / identify
終了は Ctrl+C。
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import serial
import serial.tools.list_ports

import usb_proto as proto

BAUD = 115200


def list_ports() -> list[str]:
    """ATOMS3（VID 303A）を先頭にして COM 名を返す。"""
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=lambda p: (0 if "303A" in (p.hwid or "") else 1, p.device))
    return [p.device for p in ports]


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def emit(prefix: str, text: str, lock: threading.Lock) -> None:
    with lock:
        print(f"{stamp()}  {prefix} {text}", flush=True)


def recv_loop(ser: serial.Serial, lock: threading.Lock, stop: threading.Event) -> None:
    parser = proto.FrameParser()
    try:
        while not stop.is_set():
            try:
                waiting = ser.in_waiting
                chunk = ser.read(waiting if waiting > 0 else 256)
            except serial.SerialException as exc:
                emit("!", f"COM 読みエラー  {exc}", lock)
                stop.set()
                return
            if not chunk:
                continue
            for msg_type, payload in parser.feed(chunk):
                emit(">", proto.format_rx(msg_type, payload), lock)
    finally:
        stop.set()


def main() -> int:
    parser = argparse.ArgumentParser(description="足裏 USB の送受信を解釈して表示する")
    parser.add_argument("port", nargs="?", help="COM 名。省略時は ATOMS3 を自動選択")
    args = parser.parse_args()

    port = args.port
    if not port:
        found = list_ports()
        if not found:
            print("ATOMS3 の COM が見つかりません", file=sys.stderr)
            return 1
        port = found[0]
        print(f"port {port}")

    try:
        ser = serial.Serial(port, BAUD, timeout=0.05)
    except serial.SerialException as exc:
        print(f"開けません: {exc}", file=sys.stderr)
        return 1

    lock = threading.Lock()
    stop = threading.Event()
    th = threading.Thread(target=recv_loop, args=(ser, lock, stop), daemon=True)
    th.start()
    ser.write(proto.cmd_ping())
    ser.flush()
    emit("<", "PING", lock)

    try:
        while not stop.is_set():
            line = sys.stdin.readline()
            if line == "":
                break
            cmd = line.strip().lower()
            if cmd in ("ping", "p"):
                ser.write(proto.cmd_ping())
                ser.flush()
                emit("<", "PING", lock)
            elif cmd in ("identify", "id"):
                ser.write(proto.cmd_identify())
                ser.flush()
                emit("<", "IDENTIFY", lock)
            elif cmd in ("q", "quit", "exit"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        try:
            ser.close()
        except serial.SerialException:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
