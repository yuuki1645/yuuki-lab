#!/usr/bin/env python3
"""
rt-usb バイナリフレームの組み立て／分解（ファーム usb_proto.hpp と欄を揃える）。

フレーム: AA 55 | type | len_lo | len_hi | payload | crc16_le
CRC は type+len16+payload（CRC-16-CCITT、初期値 0xFFFF）。
len は LE uint16（ver=10。8 関節×8 INA + 足 4 隅が 255 を超えるため）。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
MAGIC = b"\xAA\x55"
MAX_PAYLOAD = 512
FW_VER = 10
MAP_CHUNK = 16
JOINTS = 8
INA_CHS = 8
# 既定プロファイルで INA を付ける軸数（PaHub 0x71 CH0/CH1）
INA_DEFAULT_ASSIGNED = 2
# magic2 + type + len2 + crc2
FRAME_OVERHEAD = 7

# ボード → PC
MSG_TELEMETRY = 0x01
MSG_HELLO = 0x02
MSG_SCAN_BEGIN = 0x03
MSG_SCAN_NODE = 0x04
MSG_SCAN_END = 0x05
MSG_PROF = 0x06
MSG_PROF_OK = 0x07
MSG_PROF_ERR = 0x08
MSG_MAP_CHUNK = 0x09
MSG_MAP_OK = 0x0A
MSG_MAP_ERR = 0x0B
MSG_MODE = 0x0C
MSG_CAL_START = 0x0D
MSG_CAL_PROG = 0x0E
MSG_CAL_OK = 0x0F
MSG_CAL_ERR = 0x10
MSG_EVT_OC = 0x11
MSG_EVT_BTN = 0x12
MSG_IDENTIFY_OK = 0x13
MSG_PROBE = 0x14

# PC → ボード
CMD_PING = 0x80
CMD_SCAN = 0x81
CMD_IDENTIFY = 0x82
CMD_HOLD = 0x83
CMD_CALABORT = 0x84
CMD_CAL = 0x85
CMD_MODE = 0x86
CMD_OUT = 0x87
CMD_JOINT = 0x88
CMD_PROBE = 0x89
CMD_PROFGET = 0x8A
CMD_PROFDEFAULT = 0x8B
CMD_PROFPUT = 0x8C
CMD_MAPGET = 0x8D
CMD_MAPCHUNK = 0x8E

REASON = {
    0: "ok",
    1: "settle",
    2: "as5600",
    3: "full",
    4: "badch",
    5: "servo",
    6: "abort",
    7: "first",
    8: "fit",
    9: "map",
    10: "nvs",
    11: "busy",
    12: "short",
    13: "badarg",
    14: "count",
    15: "bad",
}

KIND_NAME = {
    0: "unknown",
    1: "pahub",
    2: "as5600",
    3: "ina226",
    4: "servo",
    5: "foot",
}

MAG_LABEL = {
    0: "OK",
    1: "磁石なし",
    2: "弱い",
    3: "強い",
    4: "I2C",
    255: "—",
}

def _telem_struct(n_j: int, n_ina: int, with_foot: bool = False) -> struct.Struct:
    """n_j 関節 + n_ina 電源枠の UsbTelemetry。with_foot は ver=10 の右足 4 隅。"""
    base = f"<7I i B {4 * n_j}f {4 * n_j}B {3 * n_ina}f {n_ina}B HBBB"
    if with_foot:
        return struct.Struct(base + " BB I 4H")
    return struct.Struct(base)


# サイズで判別。現行 ver=10 は (8, 8) + 足。旧ペイロードも残す
def _telem_layout(n_j: int, n_ina: int, with_foot: bool = False) -> tuple[int, int, bool, struct.Struct]:
    st = _telem_struct(n_j, n_ina, with_foot)
    return (n_j, n_ina, with_foot, st)


_TELEM_BY_SIZE: dict[int, tuple[int, int, bool, struct.Struct]] = {}
for _nj, _ni, _foot in ((8, 8, True), (8, 8, False), (8, 2, False), (2, 2, False)):
    _n_j, _n_ina, _has_foot, _st = _telem_layout(_nj, _ni, _foot)
    _TELEM_BY_SIZE[_st.size] = (_n_j, _n_ina, _has_foot, _st)
_TELEM = _telem_struct(JOINTS, INA_CHS, True)
_FOOT = struct.Struct("<BbB")
_HELLO = struct.Struct("<6B")
_SCAN_NODE = struct.Struct("<BbBBBB")
_ROUTE = struct.Struct("<BbBBbBBBbB")
_PROF_OK = struct.Struct("<BB")
_MAP_HDR = struct.Struct("<BHHB")
_MAP_PT = struct.Struct("<ff")
_MAP_OK = struct.Struct("<BH")
_MAP_ERR = struct.Struct("<bHHB")
_MODE = struct.Struct("<BB")
_CAL_START = struct.Struct("<B")
_CAL_PROG = struct.Struct("<BB f")
_CAL_OK = struct.Struct("<BHff")
_CAL_ERR = struct.Struct("<bB")
_EVT_OC = struct.Struct("<f")
# found, hub, ch, addr, f0, f1, f2, mag, agc, magnitude, ok
_PROBE = struct.Struct("<BBbBfffBBHB")
_CMD_CAL = struct.Struct("<B")
_CMD_MODE = struct.Struct("<B")
_CMD_OUT = struct.Struct("<BB")
_CMD_JOINT = struct.Struct("<Bf")
_CMD_PROBE = struct.Struct("<BBb")
_CMD_MAPGET = struct.Struct("<B")


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
    """type+payload を 1 フレームにする（len は LE uint16）。"""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too long")
    plen = len(payload)
    head = bytes((msg_type, plen & 0xFF, (plen >> 8) & 0xFF)) + payload
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
        # ゴミが溜まりすぎたら先頭を捨てて再同期
        if len(self._buf) > 4096:
            self.dropped_bytes += len(self._buf)
            self._buf.clear()
        return out

    def _pop_one(self) -> tuple[int, bytes] | None:
        buf = self._buf
        # マジックを探す
        while True:
            if len(buf) < FRAME_OVERHEAD:
                return None
            if buf[0] == 0xAA and buf[1] == 0x55:
                break
            del buf[0]
            self.dropped_bytes += 1
        plen = buf[3] | (buf[4] << 8)
        need = FRAME_OVERHEAD + plen
        if plen > MAX_PAYLOAD:
            del buf[0]
            self.dropped_bytes += 1
            return None
        if len(buf) < need:
            return None
        body = bytes(buf[2 : 5 + plen])  # type+len16+payload
        crc_got = buf[5 + plen] | (buf[6 + plen] << 8)
        if crc16(body) != crc_got:
            del buf[0]
            self.dropped_bytes += 1
            return None
        msg_type = buf[2]
        payload = bytes(buf[5 : 5 + plen])
        del buf[:need]
        return msg_type, payload


# ---------------------------------------------------------------------------
# 送信（PC → ボード）
# ---------------------------------------------------------------------------
def cmd_ping() -> bytes:
    return encode_frame(CMD_PING)


def cmd_scan() -> bytes:
    return encode_frame(CMD_SCAN)


def cmd_identify() -> bytes:
    return encode_frame(CMD_IDENTIFY)


def cmd_hold() -> bytes:
    return encode_frame(CMD_HOLD)


def cmd_cal_abort() -> bytes:
    return encode_frame(CMD_CALABORT)


def cmd_cal(ch: int) -> bytes:
    return encode_frame(CMD_CAL, _CMD_CAL.pack(ch))


def cmd_mode(robot: bool) -> bytes:
    return encode_frame(CMD_MODE, _CMD_MODE.pack(1 if robot else 0))


def cmd_out(ch: int | None, on: bool) -> bytes:
    """ch=None は全軸。"""
    c = 0xFF if ch is None else int(ch)
    return encode_frame(CMD_OUT, _CMD_OUT.pack(c, 1 if on else 0))


def cmd_joint(ch: int, deg: float) -> bytes:
    return encode_frame(CMD_JOINT, _CMD_JOINT.pack(ch, float(deg)))


def cmd_probe_root(addr: int) -> bytes:
    return encode_frame(CMD_PROBE, _CMD_PROBE.pack(0, addr & 0xFF, 0))


def cmd_probe_hub(hub: int, ch: int) -> bytes:
    return encode_frame(CMD_PROBE, _CMD_PROBE.pack(1, hub & 0xFF, int(ch)))


def cmd_prof_get() -> bytes:
    return encode_frame(CMD_PROFGET)


def cmd_prof_default() -> bytes:
    return encode_frame(CMD_PROFDEFAULT)


def cmd_prof_put(
    routes: list[tuple[int, int, int, int, int, int, int, int, int, int]],
    foot: tuple[int, int, int] = (0x71, 2, 0x28),
) -> bytes:
    """
    routes の各要素は
    (enc_hub, enc_ch, enc_addr, act_hub, act_ch, act_addr, servo_ch, ina_hub, ina_ch, ina_addr)。
    ina_addr=0 は未割当。
    foot は (hub, ch, addr)。addr=0 は右足スレーブ無効。
    """
    n = len(routes)
    payload = bytes((n,)) + b"".join(
        _ROUTE.pack(eh, ec, ea, ah, ac, aa, sc, ih, ic, ia)
        for eh, ec, ea, ah, ac, aa, sc, ih, ic, ia in routes
    )
    fh, fc, fa = foot
    payload += _FOOT.pack(fh, fc, fa)
    return encode_frame(CMD_PROFPUT, payload)


def cmd_map_get(ch: int) -> bytes:
    return encode_frame(CMD_MAPGET, _CMD_MAPGET.pack(ch))


def cmd_map_chunks(ch: int, points: list[tuple[float, float]]) -> list[bytes]:
    """校正点を MAP_CHUNK 件ずつのフレームにする。"""
    total = len(points)
    frames: list[bytes] = []
    start = 0
    while start < total:
        n = min(MAP_CHUNK, total - start)
        hdr = _MAP_HDR.pack(ch, total, start, n)
        body = hdr + b"".join(_MAP_PT.pack(x, y) for x, y in points[start : start + n])
        frames.append(encode_frame(CMD_MAPCHUNK, body))
        start += n
    if total == 0:
        frames.append(encode_frame(CMD_MAPCHUNK, _MAP_HDR.pack(ch, 0, 0, 0)))
    return frames


# ---------------------------------------------------------------------------
# 受信の解釈
# ---------------------------------------------------------------------------
@dataclass
class Telemetry:
    seq: int
    period_us: int
    loop_us: int
    sense_us: int
    state_us: int
    policy_us: int
    act_us: int
    jitter_us: int
    overrun: bool
    cmd: list[float]
    raw: list[float | None]
    unwrap: list[float | None]
    corr: list[float | None]
    as_ok: list[bool]
    map_ok: list[bool]
    mag: list[int]
    agc: list[int]
    volt: list[float | None]
    amp: list[float | None]
    watt: list[float | None]
    ina_ok: list[bool]
    i2c_err: int
    servo_ok: bool
    mode: str
    out_mask: int
    foot_ok: bool = False
    foot_mask: int = 0
    foot_seq: int = 0
    foot_mv: list[int] = field(default_factory=lambda: [0, 0, 0, 0])


@dataclass
class Hello:
    ver: int
    mode: str
    joints: int
    ina: int
    servo: int
    out_mask: int

    def text(self) -> str:
        m = "robot" if self.mode == "robot" else "lab"
        return (
            f"rt-usb ver={self.ver} {m} joints={self.joints} "
            f"ina={self.ina} servo={self.servo} out={self.out_mask}"
        )


@dataclass
class ScanNodeBin:
    hub: int
    ch: int
    addr: int
    kind: int
    mag: int
    agc: int


@dataclass
class FootRouteBin:
    hub: int
    ch: int
    addr: int


@dataclass
class RouteBin:
    enc_hub: int
    enc_ch: int
    enc_addr: int
    act_hub: int
    act_ch: int
    act_addr: int
    servo_ch: int
    ina_hub: int
    ina_ch: int
    ina_addr: int


@dataclass
class MapChunk:
    ch: int
    total: int
    start: int
    points: list[tuple[float, float]]


@dataclass
class Probe:
    found: int
    hub: int
    ch: int
    addr: int
    f0: float
    f1: float
    f2: float
    mag: int
    agc: int
    magnitude: int
    ok: bool


def _mode_name(v: int) -> str:
    return "robot" if v else "lab"


def _opt_float(ok: bool, x: float) -> float | None:
    if not ok:
        return None
    if x != x:  # nan
        return None
    return float(x)


def decode_telemetry(payload: bytes) -> Telemetry | None:
    layout = _TELEM_BY_SIZE.get(len(payload))
    if layout is None:
        return None
    n_got, n_ina, with_foot, st = layout
    u = st.unpack(payload)
    seq, period, loop, sense, state, policy, act, jitter, overrun = u[0:9]
    nfloat = 4 * n_got
    floats = u[9 : 9 + nfloat]
    flags = u[9 + nfloat : 9 + nfloat + nfloat]
    pwr_n = 3 * n_ina
    pwr = u[9 + 2 * nfloat : 9 + 2 * nfloat + pwr_n]
    ina_ok_t = u[9 + 2 * nfloat + pwr_n : 9 + 2 * nfloat + pwr_n + n_ina]
    tail0 = 9 + 2 * nfloat + pwr_n + n_ina
    i2c_err, servo, mode, out_mask = u[tail0 : tail0 + 4]
    foot_ok = False
    foot_mask = 0
    foot_seq = 0
    foot_mv = [0, 0, 0, 0]
    if with_foot:
        foot_ok_b, foot_mask, foot_seq, mv0, mv1, mv2, mv3 = u[tail0 + 4 : tail0 + 11]
        foot_ok = bool(foot_ok_b)
        foot_mv = [int(mv0), int(mv1), int(mv2), int(mv3)]
    as_ok = [bool(flags[i]) for i in range(n_got)]
    map_ok = [bool(flags[n_got + i]) for i in range(n_got)]
    mag = [int(flags[2 * n_got + i]) for i in range(n_got)]
    agc = [int(flags[3 * n_got + i]) for i in range(n_got)]
    ina_ok = [bool(ina_ok_t[i]) for i in range(n_ina)]

    def _pad(xs: list, fill, n: int = JOINTS):
        out = list(xs)
        while len(out) < n:
            out.append(fill)
        return out[:n]

    cmd = _pad([float(floats[i]) for i in range(n_got)], None)
    raw = _pad([_opt_float(as_ok[i], floats[n_got + i]) for i in range(n_got)], None)
    unwrap = _pad([_opt_float(as_ok[i], floats[2 * n_got + i]) for i in range(n_got)], None)
    corr = _pad([_opt_float(as_ok[i], floats[3 * n_got + i]) for i in range(n_got)], None)
    return Telemetry(
        seq=seq,
        period_us=period,
        loop_us=loop,
        sense_us=sense,
        state_us=state,
        policy_us=policy,
        act_us=act,
        jitter_us=jitter,
        overrun=bool(overrun),
        cmd=cmd,
        raw=raw,
        unwrap=unwrap,
        corr=corr,
        as_ok=_pad(as_ok, False),
        map_ok=_pad(map_ok, False),
        mag=_pad(mag, 255),
        agc=_pad(agc, 255),
        volt=_pad(
            [_opt_float(ina_ok[i], pwr[i]) for i in range(n_ina)],
            None,
            INA_CHS,
        ),
        amp=_pad(
            [_opt_float(ina_ok[i], pwr[n_ina + i]) for i in range(n_ina)],
            None,
            INA_CHS,
        ),
        watt=_pad(
            [_opt_float(ina_ok[i], pwr[2 * n_ina + i]) for i in range(n_ina)],
            None,
            INA_CHS,
        ),
        ina_ok=_pad(ina_ok, False, INA_CHS),
        i2c_err=i2c_err,
        servo_ok=bool(servo),
        mode=_mode_name(mode),
        out_mask=out_mask,
        foot_ok=foot_ok,
        foot_mask=int(foot_mask),
        foot_seq=int(foot_seq),
        foot_mv=foot_mv,
    )


def decode_hello(payload: bytes) -> Hello | None:
    if len(payload) != _HELLO.size:
        return None
    ver, mode, joints, ina, servo, out_mask = _HELLO.unpack(payload)
    return Hello(ver, _mode_name(mode), joints, ina, servo, out_mask)


def decode_scan_node(payload: bytes) -> ScanNodeBin | None:
    if len(payload) != _SCAN_NODE.size:
        return None
    hub, ch, addr, kind, mag, agc = _SCAN_NODE.unpack(payload)
    return ScanNodeBin(hub, ch, addr, kind, mag, agc)


def decode_prof(payload: bytes) -> tuple[list[RouteBin], FootRouteBin] | None:
    if len(payload) < 1:
        return None
    n = payload[0]
    need = 1 + n * _ROUTE.size + _FOOT.size
    if len(payload) < need:
        return None
    out: list[RouteBin] = []
    off = 1
    for _ in range(n):
        eh, ec, ea, ah, ac, aa, sc, ih, ic, ia = _ROUTE.unpack_from(payload, off)
        out.append(RouteBin(eh, ec, ea, ah, ac, aa, sc, ih, ic, ia))
        off += _ROUTE.size
    fh, fc, fa = _FOOT.unpack_from(payload, off)
    return out, FootRouteBin(fh, fc, fa)


def decode_map_chunk(payload: bytes) -> MapChunk | None:
    if len(payload) < _MAP_HDR.size:
        return None
    ch, total, start, n = _MAP_HDR.unpack_from(payload, 0)
    pts: list[tuple[float, float]] = []
    off = _MAP_HDR.size
    for _ in range(n):
        if off + _MAP_PT.size > len(payload):
            return None
        x, y = _MAP_PT.unpack_from(payload, off)
        pts.append((x, y))
        off += _MAP_PT.size
    return MapChunk(ch, total, start, pts)


def decode_probe(payload: bytes) -> Probe | None:
    if len(payload) != _PROBE.size:
        return None
    found, hub, ch, addr, f0, f1, f2, mag, agc, magu, ok = _PROBE.unpack(payload)
    return Probe(found, hub, ch, addr, f0, f1, f2, mag, agc, magu, bool(ok))


def format_rx(msg_type: int, payload: bytes) -> str:
    """ログ／ターミナル用の日本語 1 行（解釈結果）。"""
    if msg_type == MSG_TELEMETRY:
        t = decode_telemetry(payload)
        if t is None:
            return "テレメトリ（形式不正）"
        j = []
        for i in range(JOINTS):
            if t.as_ok[i] and t.raw[i] is not None:
                j.append(f"j{i}={t.raw[i]:.2f}°")
            else:
                j.append(f"j{i}=欠測")
        ina = []
        for i in range(INA_CHS):
            if t.ina_ok[i] and t.amp[i] is not None:
                ina.append(f"j{i}INA={t.amp[i]:.2f}A")
            else:
                ina.append(f"INA{i}=なし")
        ov = " overrun" if t.overrun else ""
        foot = "足=欠測"
        if t.foot_ok:
            foot = "足=" + ",".join(str(v) for v in t.foot_mv) + "mV"
        return (
            f"テレメトリ seq={t.seq} 周期={t.period_us/1000:.2f}ms "
            f"ループ={t.loop_us/1000:.2f}ms {ov}  {' '.join(j)}  {' '.join(ina)}  "
            f"{foot}  {t.mode} out={t.out_mask}"
        )
    if msg_type == MSG_HELLO:
        h = decode_hello(payload)
        return h.text() if h else "HELLO（形式不正）"
    if msg_type == MSG_SCAN_BEGIN:
        n = payload[0] if payload else 0
        return f"スキャン開始  {n} ノード"
    if msg_type == MSG_SCAN_NODE:
        nd = decode_scan_node(payload)
        if nd is None:
            return "スキャンノード（形式不正）"
        hub = "root" if nd.hub == 0 else f"{nd.hub:02X}"
        return (
            f"ノード  {hub} CH{nd.ch}  0x{nd.addr:02X}  "
            f"{KIND_NAME.get(nd.kind, '?')}"
        )
    if msg_type == MSG_SCAN_END:
        return "スキャン終了"
    if msg_type == MSG_PROF:
        got = decode_prof(payload)
        if got is None:
            return "プロファイル（形式不正）"
        rs, foot = got
        return (
            f"プロファイル  {len(rs)} 軸  "
            f"foot={foot.hub:02X}/CH{foot.ch}/0x{foot.addr:02X}"
        )
    if msg_type == MSG_PROF_OK:
        if len(payload) >= 2:
            return f"プロファイル保存  n={payload[0]} default={payload[1]}"
        return "プロファイル保存"
    if msg_type == MSG_PROF_ERR:
        r = payload[0] if payload else 0
        return f"プロファイル失敗  {REASON.get(r, r)}"
    if msg_type == MSG_MAP_CHUNK:
        c = decode_map_chunk(payload)
        if c is None:
            return "マップ断片（形式不正）"
        return f"マップ ch{c.ch}  {c.start}+{len(c.points)}/{c.total}"
    if msg_type == MSG_MAP_OK:
        if len(payload) >= 3:
            ch, n = _MAP_OK.unpack(payload[:3])
            return f"マップ保存  ch{ch}  {n}点"
        return "マップ保存"
    if msg_type == MSG_MAP_ERR:
        if len(payload) >= _MAP_ERR.size:
            ch, got, exp, r = _MAP_ERR.unpack(payload[: _MAP_ERR.size])
            return f"マップ失敗  ch{ch}  {REASON.get(r, r)}  {got}/{exp}"
        return "マップ失敗"
    if msg_type == MSG_MODE:
        if len(payload) >= 2:
            return f"モード  {_mode_name(payload[0])}  out={payload[1]}"
        return "モード"
    if msg_type == MSG_CAL_START:
        return f"校正開始  ch{payload[0] if payload else '?'}"
    if msg_type == MSG_CAL_PROG:
        if len(payload) >= _CAL_PROG.size:
            ch, pct, cmd = _CAL_PROG.unpack(payload[: _CAL_PROG.size])
            return f"校正  ch{ch}  {pct}%  {cmd:.1f}°"
        return "校正進捗"
    if msg_type == MSG_CAL_OK:
        if len(payload) >= _CAL_OK.size:
            ch, n, rms, mx = _CAL_OK.unpack(payload[: _CAL_OK.size])
            return f"校正完了  ch{ch}  {n}点  rms={rms:.3f}  max={mx:.3f}"
        return "校正完了"
    if msg_type == MSG_CAL_ERR:
        if len(payload) >= 2:
            ch, r = _CAL_ERR.unpack(payload[:2])
            return f"校正失敗  ch{ch}  {REASON.get(r, r)}"
        return "校正失敗"
    if msg_type == MSG_EVT_OC:
        amp = _EVT_OC.unpack(payload[:4])[0] if len(payload) >= 4 else 0.0
        return f"過電流  {amp:.2f} A"
    if msg_type == MSG_EVT_BTN:
        return "本体ボタン"
    if msg_type == MSG_IDENTIFY_OK:
        return "Identify"
    if msg_type == MSG_PROBE:
        p = decode_probe(payload)
        if p is None:
            return "PROBE（形式不正）"
        where = "root" if p.hub == 0 else f"{p.hub:02X} CH{p.ch}"
        if p.found == 2:
            return (
                f"PROBE AS5600  {where}  0x{p.addr:02X}  "
                f"{p.f0:.2f}°  {MAG_LABEL.get(p.mag, p.mag)}  AGC={p.agc}"
            )
        if p.found == 3:
            return (
                f"PROBE INA  {where}  0x{p.addr:02X}  "
                f"{p.f0:.3f}V {p.f1:.3f}A {p.f2:.3f}W  ok={int(p.ok)}"
            )
        return f"PROBE なし  {where}  0x{p.addr:02X}"
    return f"type=0x{msg_type:02X}  {len(payload)}B"


def format_tx(data: bytes) -> str:
    """送信フレームを短い説明にする。"""
    if len(data) < FRAME_OVERHEAD or data[0] != 0xAA or data[1] != 0x55:
        return f"送信 {len(data)}B"
    t = data[2]
    names = {
        CMD_PING: "PING",
        CMD_SCAN: "SCAN",
        CMD_IDENTIFY: "IDENTIFY",
        CMD_HOLD: "HOLD",
        CMD_CALABORT: "CALABORT",
        CMD_CAL: "CAL",
        CMD_MODE: "MODE",
        CMD_OUT: "OUT",
        CMD_JOINT: "CMD",
        CMD_PROBE: "PROBE",
        CMD_PROFGET: "PROFGET",
        CMD_PROFDEFAULT: "PROFDEFAULT",
        CMD_PROFPUT: "PROFPUT",
        CMD_MAPGET: "MAPGET",
        CMD_MAPCHUNK: "MAPCHUNK",
    }
    return names.get(t, f"cmd=0x{t:02X}")


def parse_cli_line(text: str) -> list[bytes]:
    """
    rt_usb_log のキーボード入力。
    ping / scan / hold / identify / mode lab|robot / out 0|1 / cmd 0 135
    """
    parts = text.strip().split()
    if not parts:
        return []
    k = parts[0].lower().lstrip("#")
    if k in ("ping", "hello"):
        return [cmd_ping()]
    if k == "scan":
        return [cmd_scan()]
    if k == "identify":
        return [cmd_identify()]
    if k == "hold":
        return [cmd_hold()]
    if k == "calabort":
        return [cmd_cal_abort()]
    if k == "cal" and len(parts) >= 2:
        return [cmd_cal(int(parts[1]))]
    if k == "mode" and len(parts) >= 2:
        return [cmd_mode(parts[1].lower() == "robot")]
    if k == "out" and len(parts) >= 2:
        if len(parts) >= 3:
            return [cmd_out(int(parts[1]), parts[2] != "0")]
        return [cmd_out(None, parts[1] != "0")]
    if k == "cmd" and len(parts) >= 3:
        return [cmd_joint(int(parts[1]), float(parts[2]))]
    if k == "profget":
        return [cmd_prof_get()]
    if k == "mapget":
        ch = int(parts[1]) if len(parts) >= 2 else 0
        return [cmd_map_get(ch)]
    return []
