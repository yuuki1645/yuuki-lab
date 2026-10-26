#!/usr/bin/env python3
"""
COM を短時間だけ読み、rt-usb のフレームが流れていれば終了コード 0 で戻る。

アプリは 20 Hz でテレメトリを出し続ける。HELLO は起動時の 1 回なので、
画面の見分けはテレメトリの長さを優先する。stdout に 1 語だけ書く。

    bench    机の rt-usb（ver 14）。Hub は /atom-bench
    core     腰の CoreS3（ver 15）。Hub は /m5-telemetry
    unknown  フレームはあるが、上のどちらでもない

終了コードは 0 = フレームあり、1 = 無音（ダウンロードモード）、2 = 開けない。
ケーブルは 1 本の想定。同時に 2 台は見ない。

DTR と RTS は立てない。pyserial の既定オープンは再接続のたびにリセットする。
手順は atom-rt/tools/lib/lab_usb.py の open_atom_serial と同じ。
書き込み中にこのプロセスがポートを握り続けないよう、読み終わったら必ず閉じる。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import serial

_PY = Path(__file__).resolve().parents[1] / "py"
sys.path.insert(0, str(_PY))

import rt_usb_proto as proto  # noqa: E402

# USB-Serial-JTAG はボーレートを使わない。lab_const.BAUD と揃えてある。
_BAUD = 115200


def listen_for_rt_usb(port: str, timeout_s: float) -> tuple[int, str]:
    """(終了コード, 画面)。コード 0 のとき画面は bench / core / unknown。"""
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = _BAUD
    ser.timeout = 0.05
    ser.dsrdtr = False
    ser.rtscts = False
    ser.dtr = False
    ser.rts = False
    try:
        ser.open()
    except serial.SerialException as exc:
        print(str(exc), file=sys.stderr)
        return 2, ""
    # open が線を動かしたあとも、もう一度下ろす。
    ser.dtr = False
    ser.rts = False
    parser = proto.FrameParser()
    deadline = time.monotonic() + timeout_s
    saw_frame = False
    try:
        while time.monotonic() < deadline:
            chunk = ser.read(256)
            if not chunk:
                continue
            # 先頭がスキャン等でも、同じ 1.5 秒のあいだにテレメトリが続く。
            for msg_type, payload in parser.feed(chunk):
                saw_frame = True
                kind = proto.usb_screen_kind(msg_type, payload)
                if kind is not None:
                    return 0, kind
        if saw_frame:
            return 0, "unknown"
        return 1, ""
    finally:
        try:
            ser.close()
        except serial.SerialException:
            pass


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: usb_rt_probe.py COMx seconds", file=sys.stderr)
        return 2
    try:
        timeout_s = float(argv[2])
    except ValueError:
        print("seconds が数値ではない", file=sys.stderr)
        return 2
    if timeout_s <= 0:
        print("seconds は正の数", file=sys.stderr)
        return 2
    code, kind = listen_for_rt_usb(argv[1], timeout_s)
    # 監視はこの 1 語だけを見る。ログは stderr。
    if code == 0 and kind:
        print(kind, flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
