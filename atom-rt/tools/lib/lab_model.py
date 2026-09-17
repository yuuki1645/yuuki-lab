"""
lab_debug の GUI 用データ型（ライブラリ。直接起動しない）。

ボードの UsbTelemetry / JointRoute を Tk が扱いやすい形にする。
バイナリの正本は rt_usb_proto.py。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import df9_force
from . import rt_usb_proto as proto
from .lab_const import INA_CHS, INA_DEFAULT_ASSIGNED, JOINTS

FOOT_CORNER_KEYS = ("top_left", "top_right", "bottom_right", "bottom_left")


@dataclass
class Frame:
    """20 Hz テレメトリ 1 周期分（欠測は None / ok=False）。"""

    t: float
    seq: int
    period_us: int
    loop_us: int
    sense_us: int
    jitter_us: int
    overrun: bool
    cmd: list[float | None] = field(default_factory=lambda: [None] * JOINTS)
    raw: list[float | None] = field(default_factory=lambda: [None] * JOINTS)
    unwrap: list[float | None] = field(default_factory=lambda: [None] * JOINTS)
    corr: list[float | None] = field(default_factory=lambda: [None] * JOINTS)
    as_ok: list[bool] = field(default_factory=lambda: [False] * JOINTS)
    mag: list[int] = field(default_factory=lambda: [255] * JOINTS)
    agc: list[int] = field(default_factory=lambda: [255] * JOINTS)
    map_ok: list[bool] = field(default_factory=lambda: [False] * JOINTS)
    volt: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    amp: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    watt: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    ina_ok: list[bool] = field(default_factory=lambda: [False] * INA_CHS)
    i2c_err: int = 0
    servo_ok: bool = False
    mode: str = "lab"
    out_mask: int = 0
    foot_ok: bool = False
    foot_mask: int = 0
    foot_seq: int = 0
    foot_mv: list[int] = field(default_factory=lambda: [0, 0, 0, 0])


@dataclass
class ScanNode:
    """I2C スキャン 1 ノード。hub は 'root' または '70' のような hex 文字。"""

    hub: str
    ch: int
    addr: str
    kind: str
    mag: int
    agc: int


@dataclass
class JointRoute:
    """論理関節 → 物理経路（ボードの JointRoute と同じ並び）。"""

    enc_hub: int = 0x70
    enc_ch: int = 0
    enc_addr: int = 0x36
    act_hub: int = 0
    act_ch: int = -1
    act_addr: int = 0x25
    servo_ch: int = 0
    ina_hub: int = 0x71
    ina_ch: int = 0
    ina_addr: int = 0x41  # 0 なら未割当


@dataclass
class FootRoute:
    """右足スレーブ経路（ボードの FootRoute と同じ並び）。addr=0 は無効。"""

    hub: int = 0x71
    ch: int = 2
    addr: int = 0x28


def default_foot() -> FootRoute:
    """既定: PaHub 0x71 CH2 の 0x28。"""
    return FootRoute()


def default_routes(n: int = JOINTS) -> list[JointRoute]:
    """既定: サーボ ch i。AS5600 は 0x70 CH0〜5。INA は先頭 2 軸のみ（枠は 8）。"""
    out: list[JointRoute] = []
    for i in range(n):
        enc_on = i < 6
        ina_on = i < INA_DEFAULT_ASSIGNED
        out.append(
            JointRoute(
                enc_hub=0x70 if enc_on else 0,
                enc_ch=i if enc_on else -1,
                enc_addr=0x36 if enc_on else 0,
                act_hub=0,
                act_ch=-1,
                act_addr=0x25,
                servo_ch=i,
                ina_hub=0x71 if ina_on else 0,
                ina_ch=i if ina_on else -1,
                ina_addr=0x41 if ina_on else 0,
            )
        )
    return out


def frame_from_telem(t: proto.Telemetry) -> Frame:
    """バイナリテレメトリを GUI 用 Frame にする。欠測は None。"""
    return Frame(
        t=time.time(),
        seq=t.seq,
        period_us=t.period_us,
        loop_us=t.loop_us,
        sense_us=t.sense_us,
        jitter_us=t.jitter_us,
        overrun=t.overrun,
        cmd=list(t.cmd),
        raw=list(t.raw),
        unwrap=list(t.unwrap),
        corr=list(t.corr),
        as_ok=list(t.as_ok),
        mag=list(t.mag),
        agc=list(t.agc),
        map_ok=list(t.map_ok),
        volt=list(t.volt),
        amp=list(t.amp),
        watt=list(t.watt),
        ina_ok=list(t.ina_ok),
        i2c_err=t.i2c_err,
        servo_ok=t.servo_ok,
        mode=t.mode,
        out_mask=t.out_mask,
        foot_ok=t.foot_ok,
        foot_mask=t.foot_mask,
        foot_seq=t.foot_seq,
        foot_mv=list(t.foot_mv),
    )


def scan_node_from_bin(nd: proto.ScanNodeBin) -> ScanNode:
    """ボードのスキャンノードを木表示用にする。"""
    hub = "root" if nd.hub == 0 else f"{nd.hub:02X}"
    return ScanNode(
        hub=hub,
        ch=int(nd.ch),
        addr=f"0x{nd.addr:02X}",
        kind=proto.KIND_NAME.get(nd.kind, "unknown"),
        mag=int(nd.mag),
        agc=int(nd.agc),
    )


def route_from_bin(r: proto.RouteBin) -> JointRoute:
    return JointRoute(
        enc_hub=r.enc_hub,
        enc_ch=r.enc_ch,
        enc_addr=r.enc_addr,
        act_hub=r.act_hub,
        act_ch=r.act_ch,
        act_addr=r.act_addr,
        servo_ch=r.servo_ch,
        ina_hub=r.ina_hub,
        ina_ch=r.ina_ch,
        ina_addr=r.ina_addr,
    )


def route_tuple(r: JointRoute) -> tuple[int, int, int, int, int, int, int, int, int, int]:
    return (
        r.enc_hub, r.enc_ch, r.enc_addr,
        r.act_hub, r.act_ch, r.act_addr, r.servo_ch,
        r.ina_hub, r.ina_ch, r.ina_addr,
    )


def foot_from_bin(r: proto.FootRouteBin) -> FootRoute:
    return FootRoute(hub=r.hub, ch=r.ch, addr=r.addr)


def foot_tuple(r: FootRoute) -> tuple[int, int, int]:
    return (r.hub, r.ch, r.addr)


def route_sig(routes: list[JointRoute], foot: FootRoute | None = None) -> tuple:
    base = tuple(route_tuple(r) for r in routes[:JOINTS])
    if foot is None:
        return base
    return base + (foot_tuple(foot),)


def foot_sample_dict(f: Frame) -> dict:
    """USB の mV を Hub と同じ corners 形にする。"""
    corners: dict[str, dict | None] = {}
    total = 0.0
    for i, key in enumerate(FOOT_CORNER_KEYS):
        installed = bool(f.foot_mask & (1 << i))
        if not f.foot_ok or not installed:
            corners[key] = None
            continue
        mv = f.foot_mv[i] if i < len(f.foot_mv) else 0
        voltage = mv / 1000.0
        rs, kg = df9_force.voltage_to_force_kg(voltage)
        corners[key] = {
            "force_kg": kg,
            "force_pct": 100.0 * kg / df9_force.FORCE_MAX_KG,
            "voltage_v": voltage,
            "rs_ohm": rs,
        }
        total += kg
    return {
        "ok": bool(f.foot_ok),
        "seq": int(f.foot_seq),
        "mask": int(f.foot_mask),
        "force_kg": total,
        "corners": corners,
    }


def ina_label(hub: int, ch: int, addr: int) -> str:
    """関節タブの INA 選択表示。addr=0 は未割当。"""
    if addr == 0:
        return "なし"
    if hub == 0:
        return f"root  0x{addr:02X}"
    return f"{hub:02X} CH{ch}  0x{addr:02X}"


def parse_ina_label(text: str) -> tuple[int, int, int] | None:
    """ina_label の逆。失敗時 None。"""
    s = text.strip()
    if s in ("なし", "", "—"):
        return 0, -1, 0
    if s.startswith("root"):
        parts = s.split()
        if len(parts) < 2:
            return None
        try:
            addr = int(parts[-1], 16)
        except ValueError:
            return None
        return 0, -1, addr
    # 例: 71 CH0  0x41
    try:
        bits = s.replace("CH", " ").replace("  ", " ").split()
        hub = int(bits[0], 16)
        ch = int(bits[1])
        addr = int(bits[-1], 16)
        return hub, ch, addr
    except (ValueError, IndexError):
        return None


def scan_node_path(n: ScanNode) -> tuple[int, int, int]:
    """スキャンノードを (hub, ch, addr) にする。"""
    if n.hub == "root":
        hub, ch = 0, -1
    else:
        try:
            hub = int(str(n.hub), 16)
        except ValueError:
            hub = 0
        ch = n.ch
    try:
        addr = int(str(n.addr), 0) if str(n.addr).lower().startswith("0x") else int(str(n.addr), 16)
    except ValueError:
        addr = 0
    return hub, ch, addr
