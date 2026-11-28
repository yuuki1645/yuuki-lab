#!/usr/bin/env python3
"""CoreS3 の方策スイッチを USB で送る。推論はここではない。

腰の CoreS3 が COM につながっているサブ PC で使う。
lab_debug.py が同じ COM を開いているあいだは送れない。Hub の実機側を止めてから実行する。

起動直後のファームは方策が切れている。最初は --vx 0 のまま入れる。
前進は 0 以上 0.2 m/s 以下。ヨーは常に 0。自由な歩行は docs/sim_to_real.md の確認が合うまで出さない。

例:
  python send_policy.py --port COM5 --enable 1 --vx 0
  python send_policy.py --port COM5 --enable 0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PY = Path(__file__).resolve().parents[2] / "link" / "py"
sys.path.insert(0, str(_PY))

import rt_usb_proto as proto  # noqa: E402

try:
    import serial
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pyserial が無い。サブ PC の Python に入れてから実行する。") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="方策のオンと前進指令を CoreS3 へ送る")
    parser.add_argument("--port", required=True, help="CoreS3 の COM")
    parser.add_argument("--enable", type=int, choices=(0, 1), required=True, help="1 で入れる。0 で切る")
    parser.add_argument("--vx", type=float, default=0.0, help="前進 m/s。0〜0.2。省略時は 0")
    args = parser.parse_args()
    frame = proto.cmd_policy(bool(args.enable), args.vx)
    # DTR/RTS を立てると CoreS3 がリセットされる。lab_usb と同じく下ろす。
    ser = serial.Serial()
    ser.port = args.port
    ser.baudrate = 115200
    ser.timeout = 0.2
    ser.dtr = False
    ser.rts = False
    ser.open()
    try:
        ser.write(frame)
        ser.flush()
    finally:
        ser.close()
    state = "入" if args.enable else "切"
    print(f"方策を{state}、vx={args.vx:.3f} m/s を {args.port} へ送った。")


if __name__ == "__main__":
    main()
