#!/usr/bin/env python3
"""
rt-usb の USB フレームをターミナルに出す CLI。

GUI（rt_monitor.py / lab_debug.py）は使わない。COM は同時に 1 プロセスだけなので、
モニタを開いているときは閉じてから起動する。

  python tools/rt_usb_log.py
  python tools/rt_usb_log.py COM11

受信は解釈済み 1 行、送信も短い説明。生のバイナリは出さない。

キーボード例: ping / scan / hold / identify / mode lab|robot / out 0 1 / cmd 0 135
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

import rt_usb_proto as proto

BAUD = 115200


def list_ports() -> list[str]:
    """ATOMS3（VID 303A）を先頭にして COM 名を返す。"""
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=lambda p: (0 if "303A" in (p.hwid or "") else 1, p.device))
    return [p.device for p in ports]


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def emit(prefix: str, text: str, lock: threading.Lock) -> None:
    """1 行をすぐ端末へ出す。prefix は > 受信 / < 送信。"""
    with lock:
        print(f"{stamp()}  {prefix} {text}", flush=True)


def recv_loop(ser: serial.Serial, lock: threading.Lock, stop: threading.Event) -> None:
    """USB を読み、CRC が通ったフレームだけ > で出す。"""
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
    parser = argparse.ArgumentParser(description="rt-usb の送受信を解釈して表示する")
    parser.add_argument("port", nargs="?", help="COM 名。省略時は ATOMS3 を自動選択")
    args = parser.parse_args()

    port = args.port
    if not port:
        found = list_ports()
        if not found:
            print("COM が見つかりません", file=sys.stderr)
            return 1
        port = found[0]

    print(
        f"接続 {port}  {BAUD}  （終了: Ctrl+C  送信: ping / scan / hold / mode lab|robot …）",
        flush=True,
    )
    try:
        ser = serial.Serial(port, BAUD, timeout=0.05)
    except serial.SerialException as exc:
        print(f"開けません  {exc}", file=sys.stderr)
        return 1

    lock = threading.Lock()
    stop = threading.Event()
    rx = threading.Thread(target=recv_loop, args=(ser, lock, stop), daemon=True)
    rx.start()

    try:
        while not stop.is_set():
            line = sys.stdin.readline()
            if line == "":
                break
            body = line.strip()
            if not body:
                continue
            frames = proto.parse_cli_line(body)
            if not frames:
                emit("!", f"未知の入力  {body}  （例: ping / scan / hold / mode robot）", lock)
                continue
            try:
                for fr in frames:
                    ser.write(fr)
                ser.flush()
            except serial.SerialException as exc:
                emit("!", f"COM 書きエラー  {exc}", lock)
                break
            for fr in frames:
                emit("<", proto.format_tx(fr), lock)
    except KeyboardInterrupt:
        print(flush=True)
    finally:
        stop.set()
        try:
            ser.close()
        except serial.SerialException:
            pass
        print("切断", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
