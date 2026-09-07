#!/usr/bin/env python3
"""
足裏マスター USB バイナリフレームの組み立て／分解。

フレーム: AA 55 | type | len | payload | crc16_le
CRC は type+len+payload（CRC-16-CCITT、初期値 0xFFFF）。
ファーム include/usb_proto.hpp と欄を揃える。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = b"\xAA\x55"
MAX_PAYLOAD = 64
FW_VER = 1
CORNERS = 4

MSG_TELEMETRY = 0x01
MSG_HELLO = 0x02
MSG_EVT_BTN = 0x12
MSG_IDENTIFY_OK = 0x13

CMD_PING = 0x80
CMD_IDENTIFY = 0x82

_TELEM = struct.Struct("<4I BB H 4H")
_HELLO = struct.Struct("<4B")


def crc16(data: bytes) -> int:
    """CRC-16-CCITT（初期値 0xFFFF）。ファーム usbCrc16 と同じ。"""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def encode_frame(msg_type: int, payload: bytes = b"") -> bytes:
    """type+payload を 1 フレームにする。"""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too long")
    head = bytes((msg_type, len(payload))) + payload
    c = crc16(head)
    return MAGIC + head + bytes((c & 0xFF, c >> 8))


class FrameParser:
    """バイト列を貯めて、CRC が通ったフレームだけ返す。"""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.dropped_bytes = 0

    def feed(self, data: bytes) -> list[tuple[int, bytes]]:
        self._buf.extend(data)
        out: list[tuple[int, bytes]] = []
        while True:
            got = self._pop_one()
            if got is None:
                break
            out.append(got)
        if len(self._buf) > 4096:
            self.dropped_bytes += len(self._buf)
            self._buf.clear()
        return out

    def _pop_one(self) -> tuple[int, bytes] | None:
        buf = self._buf
        while True:
            if len(buf) < 6:
                return None
            if buf[0] == 0xAA and buf[1] == 0x55:
                break
            del buf[0]
            self.dropped_bytes += 1
        plen = buf[3]
        need = 6 + plen
        if plen > MAX_PAYLOAD:
            del buf[0]
            self.dropped_bytes += 1
            return None
        if len(buf) < need:
            return None
        body = bytes(buf[2 : 4 + plen])
        crc_got = buf[4 + plen] | (buf[5 + plen] << 8)
        if crc16(body) != crc_got:
            del buf[0]
            self.dropped_bytes += 1
            return None
        msg_type = buf[2]
        payload = bytes(buf[4 : 4 + plen])
        del buf[:need]
        return msg_type, payload


def cmd_ping() -> bytes:
    return encode_frame(CMD_PING)


def cmd_identify() -> bytes:
    return encode_frame(CMD_IDENTIFY)


@dataclass
class Telemetry:
    seq: int
    period_us: int
    loop_us: int
    i2c_us: int
    slave_ok: bool
    overrun: bool
    i2c_err: int
    mv: list[int]  # TL, TR, BR, BL [mV]


@dataclass
class Hello:
    ver: int
    corners: int
    slave_ok: bool

    def text(self) -> str:
        ok = "slave_ok" if self.slave_ok else "slave_ng"
        return f"on-foot ver={self.ver} corners={self.corners} {ok}"


def decode_telemetry(payload: bytes) -> Telemetry | None:
    if len(payload) != _TELEM.size:
        return None
    u = _TELEM.unpack(payload)
    seq, period, loop, i2c_us, slave_ok, overrun, i2c_err = u[0:7]
    mv = [int(u[7]), int(u[8]), int(u[9]), int(u[10])]
    return Telemetry(
        seq=seq,
        period_us=period,
        loop_us=loop,
        i2c_us=i2c_us,
        slave_ok=bool(slave_ok),
        overrun=bool(overrun),
        i2c_err=i2c_err,
        mv=mv,
    )


def decode_hello(payload: bytes) -> Hello | None:
    if len(payload) != _HELLO.size:
        return None
    ver, corners, slave_ok, _reserved = _HELLO.unpack(payload)
    return Hello(ver, corners, bool(slave_ok))


def format_tx(raw: bytes) -> str:
    """送信フレームの短い説明。"""
    if len(raw) < 4:
        return "tx short"
    msg = raw[2]
    names = {CMD_PING: "PING", CMD_IDENTIFY: "IDENTIFY"}
    return names.get(msg, f"CMD 0x{msg:02X}")


def format_rx(msg_type: int, payload: bytes) -> str:
    """受信フレームの短い説明。"""
    if msg_type == MSG_TELEMETRY:
        t = decode_telemetry(payload)
        if t is None:
            return "TELEMETRY 形式不正"
        mv = " ".join(str(v) for v in t.mv)
        ok = "ok" if t.slave_ok else "NG"
        return f"TELEMETRY seq={t.seq} slave={ok} mv=[{mv}] i2c_err={t.i2c_err}"
    if msg_type == MSG_HELLO:
        h = decode_hello(payload)
        return h.text() if h else "HELLO 形式不正"
    if msg_type == MSG_IDENTIFY_OK:
        return "IDENTIFY_OK"
    if msg_type == MSG_EVT_BTN:
        return "BUTTON"
    return f"MSG 0x{msg_type:02X} len={len(payload)}"
