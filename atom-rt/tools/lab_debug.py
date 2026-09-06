#!/usr/bin/env python3
"""
ATOMS3 Lite 総合デバッグ（机上ラボ / 機体の両用）。

複数の USB を同時に開き、I2C トポロジ・磁石・電源・周期・手動 PWM を見る。
Lab ではサーボは明示するまで動かない。Robot は従来どおり出力オン。

  pip install -r tools/requirements.txt
  python tools/lab_debug.py

iPad（robotics-hub の「実機テレメトリ（M5）」）へは、このプロセスが
Socket.IO :8794 で中継する。iPad 接続中は PC 側のロボット操作は表示のみ
（全停止と USB 接続／切断は残す）。
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import random
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import serial
import serial.tools.list_ports

from cal_map_io import load_map, save_map
import rt_usb_proto as proto
from m5_hub_bridge import (
    EVT_CAL,
    EVT_CONTROL,
    EVT_EVENTS,
    EVT_FRAME,
    EVT_PROFILE,
    EVT_SCAN,
    EVT_STATUS,
    M5HubBridge,
    lan_ipv4,
)

# Windows 標準。WAV を追加依存なしで再生する（ATOMS3R 移行までの暫定）
try:
    import winsound
except ImportError:
    winsound = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# 見た目
# ---------------------------------------------------------------------------
BG = "#0e1318"
CARD = "#17202a"
CARD_HI = "#1f2a36"
TEXT = "#e8eef4"
MUTED = "#8b9bb0"
GOOD = "#10ac84"
WARN = "#feca57"
BAD = "#ee5253"
CMD_COLOR = "#ff9f43"
AS_COLOR = "#54a0ff"
UNWRAP_COLOR = "#1dd1a1"
VOLT_COLOR = "#feca57"
AMP_COLOR = "#00d2d3"
WATT_COLOR = "#ff6b81"
PERIOD_COLOR = "#f5f6fa"
CORR_COLOR = "#ff4757"  # 補正角（マップ適用後）
FLASH = "#a29bfe"
# 頻繁に更新する数値用。比例フォントだと桁が変わるたびにラベル幅が揺れる
MONO = ("Consolas", 12, "bold")
MONO_MD = ("Consolas", 14, "bold")
MONO_LG = ("Consolas", 16, "bold")
# 固定文字幅。" 1234.56 °" が収まるサイズ（Tk Label の width は文字数）
METRIC_VALUE_CHARS = 11


def _value_label(parent: tk.Misc, fg: str, font: tuple = MONO, *, anchor: str = "e") -> tk.Label:
    """頻繁更新する数値用。等幅＋固定幅で桁位置とパネル幅を固定する。"""
    return tk.Label(
        parent,
        text="—",
        bg=CARD,
        fg=fg,
        font=font,
        width=METRIC_VALUE_CHARS,
        anchor=anchor,
    )


BAUD = 115200
# 論理関節数（ファーム kSnapJoints / usb_proto と揃える）
JOINTS = 8
# 同時に出す関節パネル数。各パネルで 0〜7 を選ぶ
JOINT_PANELS = 2
INA_CHS = proto.INA_CHS
INA_DEFAULT_ASSIGNED = proto.INA_DEFAULT_ASSIGNED
# 電源グラフの系列色（関節 0〜7）
INA_PLOT_COLORS = (
    "#feca57",
    "#e67e22",
    "#00d2d3",
    "#5f27cd",
    "#10ac84",
    "#ee5253",
    "#54a0ff",
    "#c8d6e5",
)
HISTORY_SEC = 20.0
PLOT_INTERVAL_S = 0.12
TARGET_MS = 50.0
# ランダム動作の既定（atoms3 robot / servo-cal に近い）
RAND_MIN_DEG = 40.0
RAND_MAX_DEG = 230.0
RAND_HOLD_MIN_S = 0.7
RAND_HOLD_MAX_S = 1.4
RAND_MIN_JUMP_DEG = 25.0
# リポジトリ直下の audio/（tools/ の親）
REPO_ROOT = Path(__file__).resolve().parent.parent
NODES_PATH = Path(__file__).resolve().parent / "lab_nodes.json"
# 右脚制御の起動アナウンス。将来は ATOMS3R AI Chatbot 側で再生する想定
BOOT_WAV = REPO_ROOT / "audio" / "right_leg_boot.wav"
# 起動後の健全チェック通過アナウンス
GREEN_WAV = REPO_ROOT / "audio" / "system_all_green.wav"
# 起動音のあとに緑音を重ねないための最短待ち（秒）
BOOT_SOUND_GAP_S = 2.8
# 緑判定に使う起動直後のテレメトリ枚数
GREEN_FRAME_NEED = 10


def play_wav(path: Path) -> bool:
    """WAV を非同期再生する。成功なら True。失敗しても例外は外に出さない。"""
    if winsound is None:
        return False
    if not path.is_file():
        return False
    try:
        winsound.PlaySound(
            str(path),
            winsound.SND_FILENAME | winsound.SND_ASYNC,
        )
        return True
    except RuntimeError:
        return False


def play_boot_sound() -> bool:
    """起動アナウンスを再生する。"""
    return play_wav(BOOT_WAV)


def play_green_sound() -> bool:
    """異常なしアナウンスを再生する。"""
    return play_wav(GREEN_WAV)

MAG_LABEL = {
    0: "OK",
    1: "磁石なし",
    2: "弱い",
    3: "強い",
    4: "I2C",
    255: "—",
}


def mag_color(code: int) -> str:
    if code == 0:
        return GOOD
    if code in (1, 4):
        return BAD
    if code in (2, 3):
        return WARN
    return MUTED


def list_ports() -> list[tuple[str, str]]:
    """(COM, 説明) ATOMS3(303A) を先頭に。"""
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=lambda p: (0 if "303A" in (p.hwid or "") else 1, p.device))
    return [(p.device, p.description or "") for p in ports]


def load_names() -> dict[str, str]:
    if not NODES_PATH.exists():
        return {}
    try:
        data = json.loads(NODES_PATH.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_names(names: dict[str, str]) -> None:
    try:
        NODES_PATH.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 1 周期分
# ---------------------------------------------------------------------------
@dataclass
class Frame:
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
    volt: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    amp: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    watt: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    ina_ok: list[bool] = field(default_factory=lambda: [False] * INA_CHS)
    i2c_err: int = 0
    servo_ok: bool = False
    mode: str = "lab"
    out_mask: int = 0


@dataclass
class ScanNode:
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
        volt=list(t.volt),
        amp=list(t.amp),
        watt=list(t.watt),
        ina_ok=list(t.ina_ok),
        i2c_err=t.i2c_err,
        servo_ok=t.servo_ok,
        mode=t.mode,
        out_mask=t.out_mask,
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


def route_sig(routes: list[JointRoute]) -> tuple:
    return tuple(route_tuple(r) for r in routes[:JOINTS])


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


# ---------------------------------------------------------------------------
# USB
# ---------------------------------------------------------------------------
class AtomWorker:
    """1 台の ATOMS3 を裏スレッドで読む（バイナリフレーム）。"""

    def __init__(self, port: str, out: queue.Queue) -> None:
        self.port = port
        self.out = out
        self._stop = threading.Event()
        self._tx: queue.Queue[bytes] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def send(self, data: bytes) -> None:
        self._tx.put(data)

    def _put(self, kind: str, payload: object) -> None:
        # テレメトリを落とすと生角が固まる。frame は余裕を大きく取る。
        q = self.out.qsize()
        limit = 500 if kind == "frame" else 200
        if q < limit:
            self.out.put((self.port, kind, payload))

    def _run(self) -> None:
        try:
            ser = serial.Serial(self.port, BAUD, timeout=0.05)
        except serial.SerialException as exc:
            self._put("error", str(exc))
            return
        self._put("status", "接続")
        parser = proto.FrameParser()
        map_acc: list[tuple[float, float]] = []
        map_ch = 0
        map_total = 0
        try:
            while not self._stop.is_set():
                try:
                    msg = self._tx.get_nowait()
                    ser.write(msg)
                    ser.flush()
                    self._put("tx", proto.format_tx(msg))
                except queue.Empty:
                    pass
                try:
                    waiting = ser.in_waiting
                    chunk = ser.read(waiting if waiting > 0 else 256)
                except serial.SerialException as exc:
                    self._put("error", str(exc))
                    break
                if not chunk:
                    continue
                for msg_type, payload in parser.feed(chunk):
                    self._feed_frame(msg_type, payload)
                    if msg_type == proto.MSG_MAP_CHUNK:
                        c = proto.decode_map_chunk(payload)
                        if c is not None:
                            if c.start == 0:
                                map_acc = list(c.points)
                                map_ch = c.ch
                                map_total = c.total
                            else:
                                map_acc.extend(c.points)
                            if c.total == 0 or (c.start + len(c.points) >= c.total):
                                self._put("map_done", (map_ch, list(map_acc)))
                                map_acc = []
                                map_total = 0
        finally:
            try:
                ser.close()
            except serial.SerialException:
                pass
            self._put("status", "切断")

    def _feed_frame(self, msg_type: int, payload: bytes) -> None:
        if msg_type == proto.MSG_TELEMETRY:
            t = proto.decode_telemetry(payload)
            if t is None:
                self._put("log", "テレメトリ（形式不正）")
                return
            self._put("frame", frame_from_telem(t))
            return
        if msg_type == proto.MSG_HELLO:
            h = proto.decode_hello(payload)
            self._put("hello", h.text() if h else "HELLO 形式不正")
            return
        if msg_type == proto.MSG_SCAN_BEGIN:
            self._put("scan_begin", None)
            return
        if msg_type == proto.MSG_SCAN_NODE:
            nd = proto.decode_scan_node(payload)
            if nd is not None:
                self._put("node", scan_node_from_bin(nd))
            return
        if msg_type == proto.MSG_SCAN_END:
            self._put("scan_end", None)
            return
        if msg_type == proto.MSG_PROF:
            rs = proto.decode_prof(payload)
            if rs is not None:
                self._put("prof", [route_from_bin(r) for r in rs])
            return
        if msg_type == proto.MSG_MAP_CHUNK:
            # 組立は _run 側。ここでは何もしない
            return
        if msg_type in (
            proto.MSG_PROF_OK,
            proto.MSG_PROF_ERR,
            proto.MSG_MAP_OK,
            proto.MSG_MAP_ERR,
            proto.MSG_CAL_START,
            proto.MSG_CAL_PROG,
            proto.MSG_CAL_OK,
            proto.MSG_CAL_ERR,
            proto.MSG_PROBE,
            proto.MSG_IDENTIFY_OK,
        ):
            text = proto.format_rx(msg_type, payload)
            if msg_type == proto.MSG_CAL_START:
                self._put("cal_start", text)
            elif msg_type == proto.MSG_CAL_PROG:
                self._put("cal_prog", text)
            elif msg_type == proto.MSG_CAL_OK:
                self._put("cal_ok", text)
            elif msg_type == proto.MSG_CAL_ERR:
                self._put("cal_err", text)
            elif msg_type == proto.MSG_PROBE:
                self._put("probe", text)
            else:
                self._put("log", text)
            return
        if msg_type == proto.MSG_MODE:
            if len(payload) >= 2:
                self._put("mode", (proto._mode_name(payload[0]), int(payload[1])))
            return
        if msg_type == proto.MSG_EVT_OC:
            self._put("evt", proto.format_rx(msg_type, payload))
            return
        if msg_type == proto.MSG_EVT_BTN:
            self._put("btn", None)
            return
        self._put("log", proto.format_rx(msg_type, payload))



# ---------------------------------------------------------------------------
# 小さな折れ線
# ---------------------------------------------------------------------------
class LinePlot(tk.Canvas):
    def __init__(self, parent: tk.Widget, title: str, ymin: float, ymax: float, yunit: str) -> None:
        super().__init__(parent, bg=CARD, highlightthickness=0, height=110)
        self.title = title
        self.ymin = ymin
        self.ymax = ymax
        self.yunit = yunit
        self.series: dict[str, deque[tuple[float, float]]] = {}
        self.colors: dict[str, str] = {}
        self.visible: dict[str, bool] = {}
        # "left"=ymin/ymax、"right"=表示中データの自動スケール（電流など単位が違う系列用）
        self.axis: dict[str, str] = {}
        self.right_units: dict[str, str] = {}
        self.guides: list[tuple[float, str]] = []
        self.bind("<Configure>", lambda _e: self.redraw())

    def add_series(self, name: str, color: str, axis: str = "left", unit: str = "") -> None:
        self.series[name] = deque()
        self.colors[name] = color
        self.visible[name] = True
        self.axis[name] = axis
        self.right_units[name] = unit

    def set_visible(self, name: str, on: bool) -> None:
        if name in self.visible:
            self.visible[name] = on

    def set_title(self, title: str) -> None:
        self.title = title

    def add_guide(self, y: float, color: str) -> None:
        self.guides.append((y, color))

    def push(self, name: str, t: float, value: float | None) -> None:
        if value is None or name not in self.series:
            return
        hist = self.series[name]
        hist.append((t, value))
        cutoff = t - HISTORY_SEC
        while hist and hist[0][0] < cutoff:
            hist.popleft()

    def clear(self) -> None:
        for hist in self.series.values():
            hist.clear()

    def _right_visible(self) -> list[str]:
        """右軸で今見えている系列名。"""
        return [
            name
            for name in self.series
            if self.axis.get(name) == "right" and self.visible.get(name, True)
        ]

    def _right_range(self) -> tuple[float, float]:
        """右軸の表示範囲。見える系列の値から少し余白を取る。"""
        vals: list[float] = []
        for name in self._right_visible():
            vals.extend(v for _t, v in self.series[name])
        if not vals:
            return 0.0, 1.0
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-6:
            pad = max(abs(hi) * 0.25, 0.05)
            return lo - pad, hi + pad
        span = hi - lo
        return lo - 0.08 * span, hi + 0.08 * span

    def _right_unit_label(self) -> str:
        units = [self.right_units.get(n, "") for n in self._right_visible()]
        units = [u for u in units if u]
        # 同じ単位が続く場合は 1 つだけ
        uniq: list[str] = []
        for u in units:
            if u not in uniq:
                uniq.append(u)
        return "/".join(uniq)

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return
        right_on = bool(self._right_visible())
        pad_l, pad_t, pad_b = 44, 22, 8
        pad_r = 52 if right_on else 8
        self.create_text(8, 10, text=self.title, fill=MUTED, anchor="w", font=("Segoe UI", 9))
        y0, y1 = pad_t, h - pad_b
        x0, x1 = pad_l, w - pad_r
        left_span = self.ymax - self.ymin
        if left_span <= 0:
            return
        rymin, rymax = self._right_range()
        right_span = rymax - rymin
        if right_span <= 0:
            right_span = 1.0
        # 左軸目盛（固定レンジ）
        for gy in (self.ymin, (self.ymin + self.ymax) / 2, self.ymax):
            yy = y1 - (gy - self.ymin) / left_span * (y1 - y0)
            self.create_text(
                pad_l - 4, yy, text=f"{gy:.0f}{self.yunit}",
                fill=MUTED, anchor="e", font=("Segoe UI", 8),
            )
        # 右軸目盛（電圧・電流・電力。単位が混在すると電流は小さく見える）
        if right_on:
            runit = self._right_unit_label()
            self.create_text(
                w - 4, 10, text=runit, fill=MUTED, anchor="e", font=("Segoe UI", 9),
            )
            for i in range(3):
                gv = rymin + right_span * i / 2.0
                yy = y1 - (gv - rymin) / right_span * (y1 - y0)
                self.create_text(
                    x1 + 4, yy, text=f"{gv:.2f}",
                    fill=MUTED, anchor="w", font=("Segoe UI", 8),
                )
        for gy, col in self.guides:
            yy = y1 - (gy - self.ymin) / left_span * (y1 - y0)
            self.create_line(x0, yy, x1, yy, fill=col, dash=(3, 3))
        now = time.time()
        t0 = now - HISTORY_SEC
        for name, hist in self.series.items():
            if not self.visible.get(name, True):
                continue
            use_right = self.axis.get(name) == "right"
            pts: list[float] = []
            for t, v in hist:
                x = x0 + (t - t0) / HISTORY_SEC * (x1 - x0)
                if use_right:
                    yy = y1 - (v - rymin) / right_span * (y1 - y0)
                else:
                    yy = y1 - (v - self.ymin) / left_span * (y1 - y0)
                pts.extend((x, yy))
            if len(pts) >= 4:
                self.create_line(*pts, fill=self.colors[name], width=1.5)


# ---------------------------------------------------------------------------
# 1 台分の状態
# ---------------------------------------------------------------------------
class AtomSession:
    def __init__(self, port: str) -> None:
        self.port = port
        self.name = ""
        self.worker: AtomWorker | None = None
        self.q: queue.Queue = queue.Queue()
        self.connected = False
        self.hello = ""
        self.mode = "lab"
        self.out_mask = 0
        self.nodes: list[ScanNode] = []
        self._scan_acc: list[ScanNode] = []
        self.routes: list[JointRoute] = default_routes()
        self.map_points: list[tuple[float, float]] = []
        self.map_ch = 0
        self.cal_status = ""
        self.events: deque[str] = deque(maxlen=200)
        self.history: deque[Frame] = deque(maxlen=400)
        self.flash_until = 0.0
        self.last_frame: Frame | None = None
        self._last_ok: list[bool | None] = [None] * JOINTS
        self._last_i2c = 0
        self.log_fp = None
        # 1 回の接続で起動音・緑音はそれぞれ一度だけ
        self._boot_sound_played = False
        self._boot_sound_at = 0.0
        self._green_sound_played = False
        self._green_sound_failed = False
        self._got_hello = False
        self._got_scan = False
        self._post_hello_frames = 0
        self._startup_overrun = False
        self._startup_overcurrent = False
        self._i2c_err_at_hello: int | None = None

    def connect(self) -> None:
        self.disconnect()
        self._reset_startup_flags()
        self.worker = AtomWorker(self.port, self.q)
        self.worker.start()
        time.sleep(0.2)
        self.worker.send(proto.cmd_ping())
        self.worker.send(proto.cmd_scan())

    def disconnect(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.connected = False
        self._reset_startup_flags()
        self.stop_log()

    def _reset_startup_flags(self) -> None:
        """接続し直したときの起動シーケンス用フラグをクリアする。"""
        self._boot_sound_played = False
        self._boot_sound_at = 0.0
        self._green_sound_played = False
        self._green_sound_failed = False
        self._got_hello = False
        self._got_scan = False
        self._post_hello_frames = 0
        self._startup_overrun = False
        self._startup_overcurrent = False
        self._i2c_err_at_hello = None

    def send(self, data: bytes) -> None:
        if self.worker is not None:
            self.worker.send(data)

    def send_map(self, ch: int, points: list[tuple[float, float]]) -> None:
        """校正点をチャンクに分けて送る。"""
        for fr in proto.cmd_map_chunks(ch, points):
            self.send(fr)

    def start_log(self, path: Path) -> None:
        self.stop_log()
        self.log_fp = path.open("w", encoding="utf-8")
        self.log_fp.write(f"# lab_debug {self.port} {datetime.now().isoformat()}\n")

    def stop_log(self) -> None:
        if self.log_fp is not None:
            self.log_fp.close()
            self.log_fp = None

    def note(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.events.appendleft(f"{stamp}  {text}")

    def pump(self) -> None:
        try:
            while True:
                port, kind, payload = self.q.get_nowait()
                if port != self.port:
                    continue
                self._handle(kind, payload)
        except queue.Empty:
            pass
        # 起動音の待ち時間が過ぎたあとに緑音を出すため、毎 tick でも判定する
        self._maybe_play_green()

    def _handle(self, kind: str, payload: object) -> None:
        if kind == "status":
            self.connected = payload == "接続"
            self.note(str(payload))
            if self.connected:
                self.send(proto.cmd_ping())
                self.send(proto.cmd_scan())
                self.send(proto.cmd_prof_get())
        elif kind == "error":
            self.connected = False
            self.note(f"ERROR  {payload}")
            self._green_sound_failed = True
        elif kind == "hello":
            self.hello = str(payload)
            self.note(str(payload))
            self._got_hello = True
            # ボード起動／接続確認の HELLO で右脚起動アナウンスを再生
            if not self._boot_sound_played:
                self._boot_sound_played = True
                self._boot_sound_at = time.time()
                if play_boot_sound():
                    self.note(f"起動音  {BOOT_WAV.name}")
                else:
                    self.note(f"起動音なし  {BOOT_WAV.name}")
            self.send(proto.cmd_prof_get())
        elif kind == "scan_begin":
            self._scan_acc = []
        elif kind == "node":
            if isinstance(payload, ScanNode):
                self._scan_acc.append(payload)
        elif kind == "scan_end":
            self.nodes = list(self._scan_acc)
            self._got_scan = True
            self.note(f"スキャン {len(self.nodes)} ノード")
            self._maybe_play_green()
        elif kind == "prof":
            routes = payload
            if isinstance(routes, list) and routes:
                merged = default_routes()
                for i, r in enumerate(routes[:JOINTS]):
                    merged[i] = r
                self.routes = merged
                self.note(f"プロファイル受信  {len(routes)} 軸")
            else:
                self.note("プロファイル不完全")
        elif kind == "map_done":
            if isinstance(payload, tuple) and len(payload) == 2:
                self.map_ch = int(payload[0])
                self.map_points = list(payload[1])
                self.note(f"マップ受信  ch{self.map_ch}  {len(self.map_points)}点")
        elif kind == "cal_start":
            self.cal_status = str(payload)
            self.note(str(payload))
        elif kind == "cal_prog":
            self.cal_status = str(payload)
        elif kind == "cal_ok":
            self.cal_status = str(payload)
            self.note(str(payload))
        elif kind == "cal_err":
            self.cal_status = str(payload)
            self.note(str(payload))
        elif kind == "frame":
            f = payload
            if isinstance(f, Frame):
                self._on_frame(f)
                self._maybe_play_green()
        elif kind == "btn":
            self.flash_until = time.time() + 2.0
            self.note("本体ボタン")
        elif kind == "evt":
            self.note(str(payload))
            self._startup_overcurrent = True
            self._green_sound_failed = True
            messagebox.showwarning("過電流", f"{self.port}: {payload}")
        elif kind == "mode":
            if isinstance(payload, tuple) and len(payload) >= 2:
                self.mode = str(payload[0])
                self.out_mask = int(payload[1])
                self.note(f"モード  {self.mode}  out={self.out_mask}")
        elif kind == "probe":
            self.note(str(payload))
        elif kind == "log":
            self.note(str(payload))
        elif kind == "tx":
            if self.log_fp:
                self.log_fp.write(f"< {payload}\n")

    def _on_frame(self, f: Frame) -> None:
        self.last_frame = f
        self.history.append(f)
        self.mode = f.mode
        self.out_mask = f.out_mask
        if self.log_fp:
            self.log_fp.write(f"> seq={f.seq} loop={f.loop_us}\n")
        if self._got_hello and self._post_hello_frames < GREEN_FRAME_NEED + 5:
            self._post_hello_frames += 1
            if self._i2c_err_at_hello is None:
                self._i2c_err_at_hello = f.i2c_err
            if f.overrun:
                self._startup_overrun = True
        for i in range(min(JOINTS, len(f.as_ok), len(self._last_ok))):
            prev = self._last_ok[i]
            if prev is True and not f.as_ok[i]:
                mag = f.mag[i] if i < len(f.mag) else 255
                self.note(f"関節{i} AS5600 欠測  mag={MAG_LABEL.get(mag, '?')}")
            self._last_ok[i] = f.as_ok[i]
        if f.i2c_err > self._last_i2c + 4:
            self.note(f"I2C エラー累計 {f.i2c_err}")
        self._last_i2c = f.i2c_err
        if f.overrun:
            self.note(f"overrun seq={f.seq} loop={f.loop_us}us")

    def _startup_health_ok(self) -> tuple[bool, str]:
        """
        起動直後の健全性。
        @return (ok, 理由)。まだ判定材料が足りなければ (False, \"wait\")。
        """
        if self._green_sound_failed:
            return False, "起動中に異常あり"
        if not self.connected or not self._got_hello:
            return False, "wait"
        if not self._got_scan:
            return False, "wait"
        if self._post_hello_frames < GREEN_FRAME_NEED:
            return False, "wait"
        if self._boot_sound_played and (time.time() - self._boot_sound_at) < BOOT_SOUND_GAP_S:
            return False, "wait"
        if self._startup_overcurrent:
            return False, "過電流"
        if self._startup_overrun:
            return False, "周期 overrun"
        f = self.last_frame
        if f is None:
            return False, "wait"
        # スキャンで見えたデバイスはテレメトリでも生きていること
        has_as = any(n.kind == "as5600" for n in self.nodes)
        has_ina = any(n.kind == "ina226" for n in self.nodes)
        if has_as:
            if not any(f.as_ok):
                return False, "AS5600 が読めない"
            if any(code in (1, 4) for code in f.mag if code != 255):
                # 磁石なし / I2C エラーは異常。弱い・強いは警告扱いなので緑は出す
                bad = [i for i, c in enumerate(f.mag) if c in (1, 4)]
                if bad:
                    return False, f"AS5600 磁石異常 ch{bad}"
        if has_ina:
            assigned = [i for i, r in enumerate(self.routes[:JOINTS]) if r.ina_addr]
            if assigned and not any(f.ina_ok[i] for i in assigned if i < len(f.ina_ok)):
                return False, "INA226 が読めない"
            if not assigned and not any(f.ina_ok):
                return False, "INA226 が読めない"
        # 起動直後に I2C エラーが急増していたら失敗
        if self._i2c_err_at_hello is not None and f.i2c_err >= self._i2c_err_at_hello + 8:
            return False, f"I2C エラー急増 ({f.i2c_err})"
        return True, "ok"

    def _maybe_play_green(self) -> None:
        """条件が揃い異常がなければ system_all_green を一度だけ再生する。"""
        if self._green_sound_played or self._green_sound_failed:
            return
        ok, why = self._startup_health_ok()
        if why == "wait":
            return
        if not ok:
            self._green_sound_failed = True
            self.note(f"起動チェック失敗  {why}")
            return
        self._green_sound_played = True
        if play_green_sound():
            self.note(f"異常なし  {GREEN_WAV.name}")
        else:
            self.note(f"異常なし（再生失敗）  {GREEN_WAV.name}")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class LabApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("yuuki-lab  総合デバッグ")
        self.configure(bg=BG)
        self.geometry("1280x820")
        self.minsize(960, 640)

        self.names = load_names()
        self.sessions: dict[str, AtomSession] = {}
        self.current: str | None = None
        self._ports_raw: list[str] = []
        self._last_plot = 0.0
        self._amp_limit = tk.DoubleVar(value=8.0)
        self._auto_scan = tk.BooleanVar(value=False)
        self._scan_job: str | None = None
        self._syncing = False
        self._tree_sig: object = None
        self._evt_sig: object = None
        self._plot_port: str | None = None
        self._last_cmd_t = [0.0] * JOINTS
        self._last_out_reassert = 0.0
        self._last_plot_seq: tuple | None = None
        self._rand_until = [0.0] * JOINTS
        self._rand_target = [135.0] * JOINTS
        # iPad が1台でも繋がったら PC のロボット操作をロックする
        self._ipad_clients = 0
        self._robot_ctrl: list[tuple[tk.Misc, str]] = []
        self._m5_last_seq: tuple | None = None
        self._m5_evt_sig: object = None
        self._m5_scan_sig: object = None
        self._m5_prof_sig: object = None
        self._m5_cal_sig: object = None
        self._m5_st_sig: object = None
        # iPad コマンド処理中は PC 操作ガードを外す（同じハンドラを再利用するため）
        self._from_ipad = False
        self._m5_bridge = M5HubBridge(
            on_command=self._m5_cmd_from_thread,
            on_clients_changed=self._m5_clients_from_thread,
        )

        self._build()
        self._m5_bridge.set_snapshot(self._m5_snapshot)
        self._m5_bridge.start()
        if self._m5_bridge.enabled:
            lan = lan_ipv4() or "<PCのLAN IP>"
            print(f"iPad: http://{lan}:5173/m5-telemetry  （ブリッジ :8794）")
        else:
            print("iPad ブリッジ無効。pip install -r tools/requirements.txt")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._tick)
        self.after(2000, self._refresh_ports)

    def _build(self) -> None:
        top = tk.Frame(self, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text="総合デバッグ", bg=CARD, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(
            side="left", padx=12, pady=8
        )
        tk.Label(
            top,
            text="机上: Lab（PWM オフ）  機体: Robot  |  複数 ATOM を USB ハブで同時接続可",
            bg=CARD,
            fg=MUTED,
        ).pack(side="left", padx=8)
        tk.Button(top, text="全停止", command=self._hold_all, bg=BAD, fg=TEXT, relief="flat").pack(
            side="right", padx=8, pady=6
        )
        tk.Button(top, text="全接続", command=self._connect_all, bg=CARD_HI, fg=TEXT, relief="flat").pack(
            side="right", padx=4, pady=6
        )
        tk.Button(top, text="更新", command=self._refresh_ports, bg=CARD_HI, fg=TEXT, relief="flat").pack(
            side="right", padx=4, pady=6
        )
        self._ipad_banner = tk.Label(
            top, text="iPad 未接続  ブリッジ :8794", bg=CARD, fg=MUTED, anchor="e"
        )
        self._ipad_banner.pack(side="right", padx=12)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        left = tk.Frame(body, bg=BG, width=280)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="ATOM（USB）", bg=BG, fg=MUTED).pack(anchor="w")
        self.port_list = tk.Listbox(
            left, bg=CARD, fg=TEXT, selectbackground=CARD_HI, relief="flat",
            font=("Segoe UI", 10), height=8,
        )
        self.port_list.pack(fill="x", pady=(0, 6))
        self.port_list.bind("<<ListboxSelect>>", self._on_select_port)

        name_row = tk.Frame(left, bg=BG)
        name_row.pack(fill="x", pady=2)
        tk.Label(name_row, text="名前", bg=BG, fg=MUTED).pack(side="left")
        self.name_var = tk.StringVar()
        tk.Entry(name_row, textvariable=self.name_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat").pack(
            side="left", fill="x", expand=True, padx=6
        )
        tk.Button(name_row, text="保存", command=self._save_name, bg=CARD_HI, fg=TEXT, relief="flat").pack(side="right")

        btn_row = tk.Frame(left, bg=BG)
        btn_row.pack(fill="x", pady=6)
        tk.Button(btn_row, text="接続", command=self._connect_sel, bg=GOOD, fg=TEXT, relief="flat").pack(
            side="left", expand=True, fill="x", padx=(0, 3)
        )
        tk.Button(btn_row, text="切断", command=self._disconnect_sel, bg=CARD_HI, fg=TEXT, relief="flat").pack(
            side="left", expand=True, fill="x", padx=3
        )
        self.identify_btn = tk.Button(
            btn_row, text="Identify", command=self._identify, bg=FLASH, fg=BG, relief="flat"
        )
        self.identify_btn.pack(side="left", expand=True, fill="x", padx=(3, 0))
        # USB 接続／切断は iPad 接続中も PC 側に残す（COM は PC 専有）

        self.card_host = tk.Frame(left, bg=BG)
        self.card_host.pack(fill="both", expand=True, pady=(8, 0))

        right = tk.Frame(body, bg=BG)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        bar = tk.Frame(right, bg=CARD)
        bar.pack(fill="x")
        self.sel_label = tk.Label(bar, text="未選択", bg=CARD, fg=TEXT, font=("Segoe UI Semibold", 12))
        self.sel_label.pack(side="left", padx=10, pady=6)
        self.hello_label = tk.Label(bar, text="", bg=CARD, fg=MUTED)
        self.hello_label.pack(side="left")
        tk.Label(bar, text="モード", bg=CARD, fg=MUTED).pack(side="left", padx=(16, 4))
        self.mode_var = tk.StringVar(value="lab")
        self.mode_combo = ttk.Combobox(
            bar, textvariable=self.mode_var, values=("lab", "robot"), width=8, state="readonly"
        )
        self.mode_combo.pack(side="left")
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode)
        self.auto_scan_cb = tk.Checkbutton(
            bar, text="自動スキャン 5s", variable=self._auto_scan, command=self._toggle_auto,
            bg=CARD, fg=TEXT, selectcolor=CARD_HI, activebackground=CARD, activeforeground=TEXT,
        )
        self.auto_scan_cb.pack(side="left", padx=10)
        self.scan_btn = tk.Button(bar, text="スキャン", command=self._scan, bg=CARD_HI, fg=TEXT, relief="flat")
        self.scan_btn.pack(side="right", padx=8, pady=4)

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True, pady=(6, 0))
        self.tab_topo = tk.Frame(nb, bg=BG)
        self.tab_prof = tk.Frame(nb, bg=BG)
        self.tab_joint = tk.Frame(nb, bg=BG)
        self.tab_cal = tk.Frame(nb, bg=BG)
        self.tab_pwr = tk.Frame(nb, bg=BG)
        self.tab_time = tk.Frame(nb, bg=BG)
        self.tab_evt = tk.Frame(nb, bg=BG)
        nb.add(self.tab_topo, text=" トポロジ ")
        nb.add(self.tab_prof, text=" 関節プロファイル ")
        nb.add(self.tab_joint, text=" 関節 / 試験 ")
        nb.add(self.tab_cal, text=" 校正 ")
        nb.add(self.tab_pwr, text=" 電源 ")
        nb.add(self.tab_time, text=" 周期 ")
        nb.add(self.tab_evt, text=" イベント / 記録 ")

        self._build_topo()
        self._build_prof()
        self._build_joint()
        self._build_cal()
        self._build_pwr()
        self._build_time()
        self._build_evt()
        self._register_robot_controls()

    def _add_robot_ctrl(self, w: tk.Misc, enabled: str = "normal") -> None:
        """iPad 接続時に無効化するウィジェット。"""
        self._robot_ctrl.append((w, enabled))

    def _register_robot_controls(self) -> None:
        """iPad 接続中に無効化するロボット操作。全停止・USB 接続は対象外。"""
        self._add_robot_ctrl(self.mode_combo, "readonly")
        self._add_robot_ctrl(self.auto_scan_cb)
        self._add_robot_ctrl(self.scan_btn)
        self._add_robot_ctrl(self.identify_btn)
        for w in self.panel_out_cb + self.panel_rand_cb:
            self._add_robot_ctrl(w)
        for w in self.panel_cmd_scale:
            self._add_robot_ctrl(w)
        for w in self.ina_combos:
            self._add_robot_ctrl(w, "readonly")
        for w in getattr(self, "topo_lock_btns", []):
            self._add_robot_ctrl(w)
        if getattr(self, "topo_ina_spin", None) is not None:
            self._add_robot_ctrl(self.topo_ina_spin)
        for w in getattr(self, "prof_lock_btns", []):
            self._add_robot_ctrl(w)
        for w in getattr(self, "prof_entries", []):
            self._add_robot_ctrl(w)
        for w in getattr(self, "cal_lock_btns", []):
            self._add_robot_ctrl(w)
        if getattr(self, "cal_ch_spin", None) is not None:
            self._add_robot_ctrl(self.cal_ch_spin)
        if getattr(self, "amp_entry", None) is not None:
            self._add_robot_ctrl(self.amp_entry)
        for w in getattr(self, "rand_entries", []):
            self._add_robot_ctrl(w)

    def _pc_locked(self) -> bool:
        """iPad が操作権を持っている（iPad 由来の処理中はロックしない）。"""
        if self._from_ipad:
            return False
        return self._ipad_clients > 0

    def _apply_pc_lock_ui(self) -> None:
        """バナーとウィジェット状態。クライアント数で判定（コマンド処理中フラグは見ない）。"""
        locked = self._ipad_clients > 0
        for w, en in self._robot_ctrl:
            try:
                w.configure(state="disabled" if locked else en)
            except tk.TclError:
                pass
        if locked:
            self._ipad_banner.configure(
                text=f"iPad 操作中（{self._ipad_clients}） PC は表示のみ / 全停止のみ",
                fg=WARN,
            )
        else:
            self._ipad_banner.configure(text="iPad 未接続  ブリッジ :8794", fg=MUTED)

    def _m5_clients_from_thread(self, n: int) -> None:
        self.after(0, lambda: self._on_ipad_clients(n))

    def _m5_cmd_from_thread(self, msg: dict) -> None:
        self.after(0, lambda m=dict(msg): self._m5_handle_cmd(m))

    def _on_ipad_clients(self, n: int) -> None:
        prev = self._ipad_clients
        self._ipad_clients = n
        self._apply_pc_lock_ui()
        if n > 0 and prev == 0:
            s = self._m5_sess()
            if s:
                s.note("iPad が操作を開始（PC は表示のみ）")
        if n == 0 and prev > 0:
            s = self._m5_sess()
            if s:
                s.note("iPad 切断。PC 操作を再開")
        self._m5_publish_status()
        self._m5_publish_control()

    def _m5_sess(self) -> AtomSession | None:
        """当面 1 台。選択中が無ければ最初の接続を使う。"""
        s = self._sess()
        if s is not None and s.connected:
            return s
        for x in self.sessions.values():
            if x.connected:
                return x
        return None

    def _m5_snapshot(self) -> dict:
        return {
            "status": self._m5_status_dict(),
            "control": self._m5_control_dict(),
            "frame": self._m5_frame_dict(),
            "scan": self._m5_scan_dict(),
            "profile": self._m5_profile_dict(),
            "events": self._m5_events_list(),
            "cal": self._m5_cal_dict(),
        }

    def _m5_status_dict(self) -> dict:
        s = self._m5_sess()
        return {
            "ipad_clients": self._ipad_clients,
            "pc_locked": self._ipad_clients > 0,
            "connected": bool(s and s.connected),
            "port": s.port if s else "",
            "name": (s.name or s.port) if s else "",
            "hello": s.hello if s else "",
            "mode": s.mode if s else self.mode_var.get(),
            "bridge_port": 8794,
        }

    def _m5_control_dict(self) -> dict:
        try:
            amp = float(self._amp_limit.get())
        except (tk.TclError, ValueError):
            amp = 8.0
        lo, hi, h0, h1, jump = self._rand_settings()
        return {
            "out": [bool(v.get()) for v in self.out_vars],
            "cmd": [float(v.get()) for v in self.cmd_vars],
            "rand": [bool(v.get()) for v in self.rand_vars],
            "amp_limit": amp,
            "auto_scan": bool(self._auto_scan.get()),
            "rand_min": lo,
            "rand_max": hi,
            "rand_hold_min": h0,
            "rand_hold_max": h1,
            "rand_jump": jump,
        }

    def _m5_frame_dict(self) -> dict | None:
        s = self._m5_sess()
        f = s.last_frame if s else None
        if f is None:
            return None
        return {
            "t": f.t,
            "seq": f.seq,
            "period_us": f.period_us,
            "loop_us": f.loop_us,
            "sense_us": f.sense_us,
            "jitter_us": f.jitter_us,
            "overrun": f.overrun,
            "cmd": list(f.cmd),
            "raw": list(f.raw),
            "unwrap": list(f.unwrap),
            "corr": list(f.corr),
            "as_ok": list(f.as_ok),
            "mag": list(f.mag),
            "agc": list(f.agc),
            "volt": list(f.volt),
            "amp": list(f.amp),
            "watt": list(f.watt),
            "ina_ok": list(f.ina_ok),
            "i2c_err": f.i2c_err,
            "servo_ok": f.servo_ok,
            "mode": f.mode,
            "out_mask": f.out_mask,
        }

    def _m5_scan_dict(self) -> dict:
        s = self._m5_sess()
        nodes = []
        if s:
            for n in s.nodes:
                nodes.append(
                    {
                        "hub": n.hub,
                        "ch": n.ch,
                        "addr": n.addr,
                        "kind": n.kind,
                        "mag": n.mag,
                        "agc": n.agc,
                    }
                )
        return {"nodes": nodes}

    def _m5_profile_dict(self) -> dict:
        s = self._m5_sess()
        routes = s.routes if s else default_routes()
        out = []
        for r in routes[:JOINTS]:
            out.append(
                {
                    "enc_hub": r.enc_hub,
                    "enc_ch": r.enc_ch,
                    "enc_addr": r.enc_addr,
                    "act_hub": r.act_hub,
                    "act_ch": r.act_ch,
                    "act_addr": r.act_addr,
                    "servo_ch": r.servo_ch,
                    "ina_hub": r.ina_hub,
                    "ina_ch": r.ina_ch,
                    "ina_addr": r.ina_addr,
                }
            )
        return {"routes": out, "ina_options": self._ina_option_list(s) if s else ["なし"]}

    def _m5_events_list(self) -> list[str]:
        s = self._m5_sess()
        if not s:
            return []
        return list(s.events)

    def _m5_cal_dict(self) -> dict:
        s = self._m5_sess()
        if not s:
            return {"status": "", "map_ch": 0, "map_count": 0}
        return {
            "status": s.cal_status,
            "map_ch": s.map_ch,
            "map_count": len(s.map_points),
        }

    def _m5_publish_status(self) -> None:
        self._m5_bridge.publish(EVT_STATUS, self._m5_status_dict())

    def _m5_publish_control(self) -> None:
        self._m5_bridge.publish(EVT_CONTROL, self._m5_control_dict())

    def _m5_publish_tick(self) -> None:
        """Tk 周期で iPad へ最新を流す。重い SCAN/PROFILE/CAL は変化時だけ。"""
        if not self._m5_bridge.enabled:
            return
        s = self._m5_sess()
        f = s.last_frame if s else None
        seq = (s.port, f.seq) if s and f else None
        if seq != self._m5_last_seq:
            self._m5_last_seq = seq
            self._m5_bridge.publish(EVT_FRAME, self._m5_frame_dict())
            self._m5_bridge.publish(EVT_CONTROL, self._m5_control_dict())
        st_sig = (
            s.port if s else "",
            bool(s and s.connected),
            s.mode if s else "",
            s.hello if s else "",
            self._ipad_clients,
        )
        if st_sig != self._m5_st_sig:
            self._m5_st_sig = st_sig
            self._m5_bridge.publish(EVT_STATUS, self._m5_status_dict())
        if s:
            ev_sig = s.events[0] if s.events else ""
            if ev_sig != self._m5_evt_sig:
                self._m5_evt_sig = ev_sig
                self._m5_bridge.publish(EVT_EVENTS, self._m5_events_list())
            scan_sig = tuple((n.hub, n.ch, n.addr, n.kind, n.mag, n.agc) for n in s.nodes)
            if scan_sig != self._m5_scan_sig:
                self._m5_scan_sig = scan_sig
                self._m5_bridge.publish(EVT_SCAN, self._m5_scan_dict())
            prof_sig = route_sig(s.routes)
            if prof_sig != self._m5_prof_sig:
                self._m5_prof_sig = prof_sig
                self._m5_bridge.publish(EVT_PROFILE, self._m5_profile_dict())
            cal_sig = (s.cal_status, s.map_ch, len(s.map_points))
            if cal_sig != self._m5_cal_sig:
                self._m5_cal_sig = cal_sig
                self._m5_bridge.publish(EVT_CAL, self._m5_cal_dict())

    def _m5_handle_cmd(self, msg: dict) -> None:
        """iPad からの操作。Tk スレッドで USB コマンドに変換する。"""
        self._from_ipad = True
        try:
            self._m5_handle_cmd_locked(msg)
        finally:
            self._from_ipad = False

    def _m5_handle_cmd_locked(self, msg: dict) -> None:
        op = str(msg.get("op") or "")
        s = self._m5_sess()
        if op == "hold":
            self._hold_all()
            self._m5_publish_control()
            return
        if s is None:
            return
        if op == "mode":
            robot = bool(msg.get("robot"))
            self.mode_var.set("robot" if robot else "lab")
            s.send(proto.cmd_mode(robot))
        elif op == "scan":
            s.send(proto.cmd_scan())
        elif op == "identify":
            s.send(proto.cmd_identify())
        elif op == "auto_scan":
            self._auto_scan.set(bool(msg.get("on")))
            self._toggle_auto()
        elif op == "out":
            j = int(msg.get("ch", 0))
            if 0 <= j < JOINTS:
                on = bool(msg.get("on"))
                self.out_vars[j].set(on)
                s.send(proto.cmd_out(j, on))
                if on:
                    s.send(proto.cmd_joint(j, float(self.cmd_vars[j].get())))
                else:
                    self.rand_vars[j].set(False)
        elif op == "joint":
            j = int(msg.get("ch", 0))
            if 0 <= j < JOINTS:
                deg = float(msg.get("deg", 135.0))
                deg = max(40.0, min(230.0, deg))
                self._syncing = True
                try:
                    self.cmd_vars[j].set(round(deg, 1))
                finally:
                    self._syncing = False
                if self.rand_vars[j].get():
                    self.rand_vars[j].set(False)
                now = time.time()
                if self.out_vars[j].get() and now - self._last_cmd_t[j] >= 0.08:
                    self._last_cmd_t[j] = now
                    s.send(proto.cmd_joint(j, deg))
        elif op == "random":
            j = int(msg.get("ch", 0))
            if 0 <= j < JOINTS:
                on = bool(msg.get("on"))
                self.rand_vars[j].set(on)
                if on:
                    if not self.out_vars[j].get():
                        self.out_vars[j].set(True)
                        s.send(proto.cmd_out(j, True))
                        s.send(proto.cmd_joint(j, float(self.cmd_vars[j].get())))
                    self._rand_until[j] = 0.0
                    s.note(f"関節{j} ランダム ON")
                else:
                    s.note(f"関節{j} ランダム OFF")
        elif op == "rand_settings":
            for key, var in (
                ("rand_min", self.rand_min_var),
                ("rand_max", self.rand_max_var),
                ("rand_hold_min", self.rand_hold_min_var),
                ("rand_hold_max", self.rand_hold_max_var),
                ("rand_jump", self.rand_jump_var),
            ):
                if key in msg:
                    try:
                        var.set(float(msg[key]))
                    except (tk.TclError, TypeError, ValueError):
                        pass
        elif op == "amp_limit":
            try:
                self._amp_limit.set(float(msg.get("amp_limit", 8.0)))
            except (tk.TclError, TypeError, ValueError):
                pass
        elif op == "probe":
            hub = str(msg.get("hub") or "root")
            ch = int(msg.get("ch", -1))
            addr = str(msg.get("addr") or "0x36")
            if hub == "root":
                try:
                    a = int(addr, 0) if addr.lower().startswith("0x") else int(addr, 16)
                except ValueError:
                    a = 0x36
                s.send(proto.cmd_probe_root(a))
            else:
                try:
                    hub_n = int(hub, 16)
                except ValueError:
                    hub_n = 0x70
                s.send(proto.cmd_probe_hub(hub_n, ch))
        elif op == "ina_assign":
            j = int(msg.get("ch", 0))
            if 0 <= j < len(s.routes):
                s.routes[j].ina_hub = int(msg.get("ina_hub", 0))
                s.routes[j].ina_ch = int(msg.get("ina_ch", -1))
                s.routes[j].ina_addr = int(msg.get("ina_addr", 0))
                self._send_routes(s, s.routes, f"INA 関節{j} ← iPad")
        elif op == "prof_get":
            s.send(proto.cmd_prof_get())
        elif op == "prof_default":
            s.send(proto.cmd_prof_default())
        elif op == "prof_from_scan":
            self._prof_from_scan()
        elif op == "prof_put":
            raw = msg.get("routes")
            if isinstance(raw, list) and raw:
                routes = default_routes()
                for i, d in enumerate(raw[:JOINTS]):
                    if not isinstance(d, dict):
                        continue
                    routes[i] = JointRoute(
                        enc_hub=int(d.get("enc_hub", 0)),
                        enc_ch=int(d.get("enc_ch", -1)),
                        enc_addr=int(d.get("enc_addr", 0)),
                        act_hub=int(d.get("act_hub", 0)),
                        act_ch=int(d.get("act_ch", -1)),
                        act_addr=int(d.get("act_addr", 0x25)),
                        servo_ch=int(d.get("servo_ch", i)),
                        ina_hub=int(d.get("ina_hub", 0)),
                        ina_ch=int(d.get("ina_ch", -1)),
                        ina_addr=int(d.get("ina_addr", 0)),
                    )
                self._send_routes(s, routes, "プロファイル送信（iPad）")
        elif op == "cal_start":
            ch = int(msg.get("ch", 0))
            s.send(proto.cmd_cal(ch))
            self.cal_status_lab.configure(text=f"状態: 開始要求 ch{ch}")
        elif op == "cal_abort":
            s.send(proto.cmd_cal_abort())
        elif op == "map_get":
            ch = int(msg.get("ch", 0))
            s.send(proto.cmd_map_get(ch))
        self._m5_publish_control()
        self._m5_publish_status()

    def _build_topo(self) -> None:
        hint = tk.Label(
            self.tab_topo,
            text="挿した Unit が木に出ます。ノードを選んで「1回読む」。机ではケーブルを抜き差しして差分を見てください。",
            bg=BG, fg=MUTED, anchor="w",
        )
        hint.pack(fill="x", padx=8, pady=6)
        cols = tk.Frame(self.tab_topo, bg=BG)
        cols.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(cols, columns=("kind", "mag", "agc"), show="tree headings", height=16)
        self.tree.heading("#0", text="場所")
        self.tree.heading("kind", text="種類")
        self.tree.heading("mag", text="磁石")
        self.tree.heading("agc", text="AGC")
        self.tree.column("#0", width=280)
        self.tree.column("kind", width=90)
        self.tree.column("mag", width=90)
        self.tree.column("agc", width=70)
        self.tree.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        side = tk.Frame(cols, bg=BG, width=200)
        side.pack(side="right", fill="y", padx=8)
        self.probe_btn = tk.Button(
            side, text="1回読む (PROBE)", command=self._probe, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.probe_btn.pack(fill="x", pady=4)
        tk.Label(side, text="INA を関節へ", bg=BG, fg=MUTED).pack(anchor="w", pady=(12, 2))
        self.topo_ina_joint = tk.IntVar(value=0)
        self.topo_ina_spin = ttk.Spinbox(
            side, from_=0, to=JOINTS - 1, textvariable=self.topo_ina_joint, width=4
        )
        self.topo_ina_spin.pack(fill="x")
        self.assign_ina_btn = tk.Button(
            side, text="選択ノードを割当", command=self._assign_ina_from_tree,
            bg=GOOD, fg=TEXT, relief="flat",
        )
        self.assign_ina_btn.pack(fill="x", pady=4)
        self.clear_ina_btn = tk.Button(
            side, text="割当を外す", command=self._clear_ina_from_tree,
            bg=CARD_HI, fg=TEXT, relief="flat",
        )
        self.clear_ina_btn.pack(fill="x", pady=2)
        self.topo_lock_btns = [self.probe_btn, self.assign_ina_btn, self.clear_ina_btn]
        tk.Label(
            side,
            text="INA226 を選んで関節番号を指定すると、20 Hz の電源監視がその経路になります。Grove 直結でも Hub 先でも可。",
            bg=BG, fg=MUTED, wraplength=180, justify="left",
        ).pack(anchor="w", pady=8)

    def _build_prof(self) -> None:
        """論理関節 → Hub/サーボ ch の対応表。焼き直しなしで配線を変えられる。"""
        hint = tk.Label(
            self.tab_prof,
            text="hub=0 は Grove 直結。enc=AS5600、act=サーボ、ina=その関節の電源監視。"
            " 変更後「ボードへ送信」で NVS に保存。ina_addr=0 は未割当。",
            bg=BG, fg=MUTED, anchor="w", wraplength=900, justify="left",
        )
        hint.pack(fill="x", padx=8, pady=6)
        btn = tk.Frame(self.tab_prof, bg=BG)
        btn.pack(fill="x", padx=8, pady=4)
        self.prof_get_btn = tk.Button(
            btn, text="ボードから取得", command=self._prof_get, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.prof_get_btn.pack(side="left", padx=(0, 6))
        self.prof_put_btn = tk.Button(
            btn, text="ボードへ送信", command=self._prof_put, bg=GOOD, fg=TEXT, relief="flat"
        )
        self.prof_put_btn.pack(side="left", padx=6)
        self.prof_default_btn = tk.Button(
            btn, text="既定に戻す", command=self._prof_default, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.prof_default_btn.pack(side="left", padx=6)
        self.prof_from_scan_btn = tk.Button(
            btn, text="SCANから仮割当", command=self._prof_from_scan, bg=FLASH, fg=BG, relief="flat"
        )
        self.prof_from_scan_btn.pack(side="left", padx=6)
        self.prof_lock_btns = [
            self.prof_get_btn, self.prof_put_btn, self.prof_default_btn, self.prof_from_scan_btn,
        ]
        self.prof_entries: list[tk.Entry] = []

        self.prof_vars: list[dict[str, tk.StringVar]] = []
        grid = tk.Frame(self.tab_prof, bg=BG)
        grid.pack(fill="x", padx=8, pady=8)
        headers = (
            "関節", "enc_hub", "enc_ch", "enc_addr",
            "act_hub", "act_ch", "act_addr", "servo_ch",
            "ina_hub", "ina_ch", "ina_addr",
        )
        for c, h in enumerate(headers):
            tk.Label(grid, text=h, bg=BG, fg=MUTED).grid(row=0, column=c, padx=4, pady=2)
        for i in range(JOINTS):
            vars_row: dict[str, tk.StringVar] = {}
            tk.Label(grid, text=str(i), bg=BG, fg=TEXT).grid(row=i + 1, column=0, padx=4)
            defaults = default_routes()[i]
            for c, (key, val) in enumerate(
                (
                    ("enc_hub", f"0x{defaults.enc_hub:02X}"),
                    ("enc_ch", str(defaults.enc_ch)),
                    ("enc_addr", f"0x{defaults.enc_addr:02X}"),
                    ("act_hub", str(defaults.act_hub)),
                    ("act_ch", str(defaults.act_ch)),
                    ("act_addr", f"0x{defaults.act_addr:02X}"),
                    ("servo_ch", str(defaults.servo_ch)),
                    ("ina_hub", f"0x{defaults.ina_hub:02X}"),
                    ("ina_ch", str(defaults.ina_ch)),
                    ("ina_addr", f"0x{defaults.ina_addr:02X}"),
                ),
                start=1,
            ):
                var = tk.StringVar(value=val)
                vars_row[key] = var
                ent = tk.Entry(
                    grid, textvariable=var, width=8, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat"
                )
                ent.grid(row=i + 1, column=c, padx=4, pady=2)
                self.prof_entries.append(ent)
            self.prof_vars.append(vars_row)
        self._prof_sig: object = None

    def _build_joint(self) -> None:
        self.joint_labs: list[dict[str, tk.Label]] = []
        self.ina_sel_vars: list[tk.StringVar] = []
        self.ina_combos: list[ttk.Combobox] = []
        # 制御状態は論理関節ごと（パネル切替で失わない）
        self.out_vars = [tk.BooleanVar(value=False) for _ in range(JOINTS)]
        self.cmd_vars = [tk.DoubleVar(value=135.0) for _ in range(JOINTS)]
        self.rand_vars = [tk.BooleanVar(value=False) for _ in range(JOINTS)]
        self.panel_joint_vars: list[tk.IntVar] = []
        self.panel_out_cb: list[tk.Checkbutton] = []
        self.panel_cmd_scale: list[tk.Scale] = []
        self.panel_rand_cb: list[tk.Checkbutton] = []
        row = tk.Frame(self.tab_joint, bg=BG)
        row.pack(fill="x", padx=8, pady=6)
        for p in range(JOINT_PANELS):
            card = tk.Frame(row, bg=CARD)
            card.pack(side="left", fill="x", expand=True, padx=4)
            # タイトルを関節番号の選択にする（0〜7）
            head = tk.Frame(card, bg=CARD)
            head.pack(anchor="w", padx=10, pady=(6, 0))
            tk.Label(head, text="関節", bg=CARD, fg=MUTED).pack(side="left")
            jv = tk.IntVar(value=p)
            self.panel_joint_vars.append(jv)
            pick = ttk.Combobox(
                head,
                textvariable=jv,
                values=tuple(range(JOINTS)),
                width=4,
                state="readonly",
            )
            pick.pack(side="left", padx=6)
            pick.bind("<<ComboboxSelected>>", lambda _e, p=p: self._on_panel_joint(p))
            labs: dict[str, tk.Label] = {}
            # 数値を 2 カラムにして縦を短くし、下のグラフへ高さを回す
            metrics = tk.Frame(card, bg=CARD)
            metrics.pack(fill="x", padx=4, pady=2)
            # uniform で左右カラム幅を固定し、数値更新で列幅が再配分されないようにする
            metrics.columnconfigure(0, weight=1, uniform="jointm")
            metrics.columnconfigure(1, weight=1, uniform="jointm")

            def _metric(parent: tk.Frame, r: int, c: int, key: str, title: str, col: str) -> None:
                # 値は等幅＋固定幅＋右寄せ。桁が変わってもセル幅と数字位置が動かない
                cell = tk.Frame(parent, bg=CARD)
                cell.grid(row=r, column=c, sticky="ew", padx=6, pady=0)
                cell.columnconfigure(1, weight=1)
                tk.Label(cell, text=title, bg=CARD, fg=MUTED, font=("Segoe UI", 9)).grid(
                    row=0, column=0, sticky="w"
                )
                lab = _value_label(cell, col)
                lab.grid(row=0, column=1, sticky="e")
                labs[key] = lab

            _metric(metrics, 0, 0, "cmd", "指令", CMD_COLOR)
            _metric(metrics, 1, 0, "raw", "生角", AS_COLOR)
            _metric(metrics, 2, 0, "unw", "unwrap", UNWRAP_COLOR)
            _metric(metrics, 3, 0, "corr", "補正", CORR_COLOR)
            _metric(metrics, 0, 1, "mag", "磁石", GOOD)
            _metric(metrics, 1, 1, "agc", "AGC", MUTED)
            _metric(metrics, 2, 1, "v", "電圧", VOLT_COLOR)
            _metric(metrics, 3, 1, "a", "電流", AMP_COLOR)
            _metric(metrics, 4, 0, "w", "電力", WATT_COLOR)
            ina_cell = tk.Frame(metrics, bg=CARD)
            ina_cell.grid(row=4, column=1, sticky="ew", padx=6, pady=0)
            tk.Label(ina_cell, text="INA226", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
            iv = tk.StringVar(value="なし")
            cb = ttk.Combobox(ina_cell, textvariable=iv, state="readonly", width=14)
            cb.pack(side="right", padx=(4, 0))
            cb.bind("<<ComboboxSelected>>", lambda _e, p=p: self._on_ina_combo(p))
            self.joint_labs.append(labs)
            self.ina_sel_vars.append(iv)
            self.ina_combos.append(cb)
            out_cb = tk.Checkbutton(
                card, text="PWM 出力する（机では必要な軸だけ）", variable=self.out_vars[p],
                command=lambda p=p: self._toggle_out(p),
                bg=CARD, fg=TEXT, selectcolor=CARD_HI, activebackground=CARD, activeforeground=TEXT,
            )
            out_cb.pack(anchor="w", padx=10, pady=(2, 0))
            self.panel_out_cb.append(out_cb)
            # 指令値は上の「指令」ラベルで見えるのでスライダ上の数字は出さない（高さ節約）
            sc = tk.Scale(
                card, from_=40, to=230, orient="horizontal", variable=self.cmd_vars[p], resolution=0.5,
                bg=CARD, fg=TEXT, troughcolor=CARD_HI, highlightthickness=0,
                showvalue=False, sliderlength=16,
                command=lambda _v, p=p: self._cmd_drag(p),
            )
            sc.pack(fill="x", padx=10, pady=(0, 0))
            self.panel_cmd_scale.append(sc)
            rand_cb = tk.Checkbutton(
                card,
                text="ランダム動作",
                variable=self.rand_vars[p],
                command=lambda p=p: self._toggle_random(p),
                bg=CARD,
                fg=WARN,
                selectcolor=CARD_HI,
                activebackground=CARD,
                activeforeground=WARN,
            )
            rand_cb.pack(anchor="w", padx=10, pady=(0, 4))
            self.panel_rand_cb.append(rand_cb)

        # ランダム共通設定（PC 側が #CMD を送る。atoms3 の random と同趣旨）
        rand_box = tk.Frame(self.tab_joint, bg=CARD)
        rand_box.pack(fill="x", padx=8, pady=(0, 2))
        tk.Label(rand_box, text="ランダム設定", bg=CARD, fg=MUTED).pack(side="left", padx=10, pady=4)
        self.rand_min_var = tk.DoubleVar(value=RAND_MIN_DEG)
        self.rand_max_var = tk.DoubleVar(value=RAND_MAX_DEG)
        self.rand_hold_min_var = tk.DoubleVar(value=RAND_HOLD_MIN_S)
        self.rand_hold_max_var = tk.DoubleVar(value=RAND_HOLD_MAX_S)
        self.rand_jump_var = tk.DoubleVar(value=RAND_MIN_JUMP_DEG)
        self.rand_entries: list[tk.Entry] = []
        for label, var, width in (
            ("最小°", self.rand_min_var, 5),
            ("最大°", self.rand_max_var, 5),
            ("保持min秒", self.rand_hold_min_var, 5),
            ("保持max秒", self.rand_hold_max_var, 5),
            ("最小ジャンプ°", self.rand_jump_var, 5),
        ):
            tk.Label(rand_box, text=label, bg=CARD, fg=MUTED).pack(side="left", padx=(8, 2))
            ent = tk.Entry(
                rand_box, textvariable=var, width=width, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, relief="flat"
            )
            ent.pack(side="left")
            self.rand_entries.append(ent)
        tk.Label(
            rand_box,
            text="PWM ON の軸だけ動く。スライダ操作でその軸のランダムはオフ",
            bg=CARD,
            fg=MUTED,
        ).pack(side="left", padx=12)

        # 角度グラフ: 表示する関節を選び、各系列をトグル
        plot_bar = tk.Frame(self.tab_joint, bg=BG)
        plot_bar.pack(fill="x", padx=8, pady=(4, 0))
        tk.Label(plot_bar, text="グラフ関節", bg=BG, fg=MUTED).pack(side="left")
        self.plot_joint_var = tk.IntVar(value=0)
        joint_box = ttk.Combobox(
            plot_bar,
            textvariable=self.plot_joint_var,
            values=tuple(range(JOINTS)),
            width=4,
            state="readonly",
        )
        joint_box.pack(side="left", padx=6)
        joint_box.bind("<<ComboboxSelected>>", self._on_plot_joint)

        # 角度は左軸（0–360°）。電源は右軸（見える系列で自動スケール）
        self.plot_line_vars: dict[str, tk.BooleanVar] = {
            "cmd": tk.BooleanVar(value=True),
            "raw": tk.BooleanVar(value=False),
            "unw": tk.BooleanVar(value=False),
            "corr": tk.BooleanVar(value=True),
            "v": tk.BooleanVar(value=False),
            "a": tk.BooleanVar(value=True),
            "w": tk.BooleanVar(value=False),
        }
        for key, title, col in (
            ("cmd", "指令", CMD_COLOR),
            ("raw", "生角", AS_COLOR),
            ("unw", "unwrap", UNWRAP_COLOR),
            ("corr", "補正", CORR_COLOR),
        ):
            tk.Checkbutton(
                plot_bar,
                text=title,
                variable=self.plot_line_vars[key],
                command=self._on_plot_lines,
                bg=BG,
                fg=col,
                selectcolor=CARD_HI,
                activebackground=BG,
                activeforeground=col,
            ).pack(side="left", padx=6)
        tk.Label(plot_bar, text="|", bg=BG, fg=MUTED).pack(side="left", padx=4)
        for key, title, col in (
            ("v", "電圧", VOLT_COLOR),
            ("a", "電流", AMP_COLOR),
            ("w", "電力", WATT_COLOR),
        ):
            tk.Checkbutton(
                plot_bar,
                text=title,
                variable=self.plot_line_vars[key],
                command=self._on_plot_lines,
                bg=BG,
                fg=col,
                selectcolor=CARD_HI,
                activebackground=BG,
                activeforeground=col,
            ).pack(side="left", padx=6)

        self.plot_ang = LinePlot(self.tab_joint, "関節0  左:°  右:電源", 0, 360, "°")
        self.plot_ang.add_series("cmd", CMD_COLOR)
        self.plot_ang.add_series("raw", AS_COLOR)
        self.plot_ang.add_series("unw", UNWRAP_COLOR)
        self.plot_ang.add_series("corr", CORR_COLOR)
        self.plot_ang.add_series("v", VOLT_COLOR, axis="right", unit="V")
        self.plot_ang.add_series("a", AMP_COLOR, axis="right", unit="A")
        self.plot_ang.add_series("w", WATT_COLOR, axis="right", unit="W")
        # 電源系列は既定で電流だけ出す（電圧と同時だと電流が潰れる）
        self.plot_ang.set_visible("raw", False)
        self.plot_ang.set_visible("unw", False)
        self.plot_ang.set_visible("v", False)
        self.plot_ang.set_visible("w", False)
        # パネルを縮めた分、グラフの希望高さを上げて下側を広く取る
        self.plot_ang.configure(height=220)
        self.plot_ang.pack(fill="both", expand=True, padx=8, pady=(4, 6))

    def _plot_joint_index(self) -> int:
        try:
            j = int(self.plot_joint_var.get())
        except (tk.TclError, ValueError):
            return 0
        return max(0, min(JOINTS - 1, j))

    def _panel_joint(self, panel: int) -> int:
        """パネル panel が今表示している論理関節番号。"""
        if panel < 0 or panel >= len(self.panel_joint_vars):
            return 0
        try:
            j = int(self.panel_joint_vars[panel].get())
        except (tk.TclError, ValueError):
            return panel
        return max(0, min(JOINTS - 1, j))

    def _bind_panel_joint_widgets(self, panel: int) -> None:
        """パネルのチェック／スライダを、選択中の関節の変数に付け替える。"""
        j = self._panel_joint(panel)
        if panel < len(self.panel_out_cb):
            self.panel_out_cb[panel].configure(variable=self.out_vars[j])
        if panel < len(self.panel_cmd_scale):
            self.panel_cmd_scale[panel].configure(variable=self.cmd_vars[j])
        if panel < len(self.panel_rand_cb):
            self.panel_rand_cb[panel].configure(variable=self.rand_vars[j])

    def _on_panel_joint(self, panel: int, _evt: object = None) -> None:
        """パネルの関節番号が変わったら、操作対象と表示を付け替える。"""
        self._bind_panel_joint_widgets(panel)
        s = self._sess()
        if s:
            self._refresh_ina_combos(s)
            if s.last_frame is not None:
                self._fill_joint_panel(s.last_frame, panel)

    def _on_plot_joint(self, _evt: object = None) -> None:
        j = self._plot_joint_index()
        self.plot_ang.clear()
        self.plot_ang.set_title(f"関節{j}  左:°  右:電源")
        self.plot_ang.redraw()

    def _on_plot_lines(self) -> None:
        for key, var in self.plot_line_vars.items():
            self.plot_ang.set_visible(key, bool(var.get()))
        self.plot_ang.redraw()

    def _build_cal(self) -> None:
        """サーボ↔AS5600 の 1° マップ校正。実機が 40〜230° を往復する。"""
        hint = tk.Label(
            self.tab_cal,
            text="周囲を空けてから実行。40→230→40°（1°・静止待ち）でマップを作り NVS に保存し、続けて #MAP を送出します。"
            " 所要約数分。中断は「中止」または全停止。",
            bg=BG, fg=MUTED, anchor="w", wraplength=900, justify="left",
        )
        hint.pack(fill="x", padx=8, pady=6)

        row = tk.Frame(self.tab_cal, bg=BG)
        row.pack(fill="x", padx=8, pady=4)
        tk.Label(row, text="関節", bg=BG, fg=MUTED).pack(side="left")
        self.cal_ch_var = tk.IntVar(value=0)
        self.cal_ch_spin = ttk.Spinbox(row, from_=0, to=JOINTS - 1, textvariable=self.cal_ch_var, width=4)
        self.cal_ch_spin.pack(side="left", padx=8)
        self.cal_start_btn = tk.Button(
            row, text="校正開始", command=self._cal_start, bg=WARN, fg=BG, relief="flat"
        )
        self.cal_start_btn.pack(side="left", padx=6)
        # 中止は全停止と同様に PC からも残す
        tk.Button(row, text="中止", command=self._cal_abort, bg=BAD, fg=TEXT, relief="flat").pack(
            side="left", padx=6
        )

        self.cal_status_lab = tk.Label(self.tab_cal, text="状態: —", bg=BG, fg=TEXT, anchor="w")
        self.cal_status_lab.pack(fill="x", padx=8, pady=4)
        self.cal_map_lab = tk.Label(self.tab_cal, text="マップ: （未受信）", bg=BG, fg=MUTED, anchor="w")
        self.cal_map_lab.pack(fill="x", padx=8, pady=2)

        io = tk.Frame(self.tab_cal, bg=BG)
        io.pack(fill="x", padx=8, pady=10)
        self.map_get_btn = tk.Button(
            io, text="ボードからマップ取得", command=self._map_get, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.map_get_btn.pack(side="left", padx=(0, 6))
        self.map_save_btn = tk.Button(
            io, text="JSON に保存", command=self._map_save_json, bg=CARD_HI, fg=TEXT, relief="flat"
        )
        self.map_save_btn.pack(side="left", padx=6)
        self.map_load_btn = tk.Button(
            io, text="JSON を開いて送信", command=self._map_load_json, bg=GOOD, fg=TEXT, relief="flat"
        )
        self.map_load_btn.pack(side="left", padx=6)
        self.cal_lock_btns = [
            self.cal_start_btn, self.map_get_btn, self.map_save_btn, self.map_load_btn,
        ]
        self._cal_status_sig = ""
        self._cal_map_sig: object = None

    def _cal_start(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        ch = int(self.cal_ch_var.get())
        if not messagebox.askokcancel(
            "校正",
            f"関節 {ch} を 40→230→40° で動かします。\n"
            "干渉・配線を確認しましたか？\n（数分かかります）",
        ):
            return
        # Lab でも校正中はボードが当該軸の PWM を一時オンする
        s.send(proto.cmd_cal(ch))
        s.note(f"校正開始要求  ch{ch}")
        self.cal_status_lab.configure(text=f"状態: 開始要求 ch{ch}")

    def _cal_abort(self) -> None:
        s = self._sess()
        if s:
            s.send(proto.cmd_cal_abort())
            s.note("校正中止要求")

    def _map_get(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        ch = int(self.cal_ch_var.get())
        s.send(proto.cmd_map_get(ch))
        s.note(f"マップ取得  ch{ch}")

    def _map_save_json(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s or len(s.map_points) < 2:
            messagebox.showinfo("マップ", "先にボードからマップを取得するか、校正を完了してください。")
            return
        path = filedialog.asksaveasfilename(
            title="校正マップを保存",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"cal_map_ch{s.map_ch}.json",
        )
        if not path:
            return
        save_map(path, s.map_ch, s.map_points)
        s.note(f"マップ保存  {path}  {len(s.map_points)}点")

    def _map_load_json(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        path = filedialog.askopenfilename(
            title="校正マップを開く",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            file_ch, points = load_map(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("マップ", str(exc))
            return
        if len(points) < 2:
            messagebox.showerror("マップ", "点が足りません")
            return
        ch = int(self.cal_ch_var.get())
        # ファイルの channel と UI が違うときは UI（送信先）を優先
        s.map_ch = ch
        s.map_points = points
        s.send_map(ch, points)
        s.note(f"マップ送信  ch{ch}  {len(points)}点  (file ch={file_ch})")
        self._refresh_cal_labels(s)

    def _refresh_cal_labels(self, s: AtomSession) -> None:
        if s.cal_status:
            self.cal_status_lab.configure(text=f"状態: {s.cal_status}")
        if s.map_points:
            self.cal_map_lab.configure(
                text=f"マップ: ch{s.map_ch}  {len(s.map_points)}点",
                fg=GOOD,
            )
        else:
            self.cal_map_lab.configure(text="マップ: （未受信）", fg=MUTED)

    def _build_pwr(self) -> None:
        lim = tk.Frame(self.tab_pwr, bg=BG)
        lim.pack(fill="x", padx=8, pady=6)
        tk.Label(lim, text="PC 側電流監視 [A]（超えたら #HOLD）", bg=BG, fg=MUTED).pack(side="left")
        self.amp_entry = tk.Entry(
            lim, textvariable=self._amp_limit, width=6, bg=CARD, fg=TEXT, insertbackground=TEXT
        )
        self.amp_entry.pack(side="left", padx=8)
        self.ina_labs: list[dict[str, tk.Label]] = []
        grid = tk.Frame(self.tab_pwr, bg=BG)
        grid.pack(fill="x", padx=8)
        for i in range(INA_CHS):
            card = tk.Frame(grid, bg=CARD)
            card.grid(row=i // 4, column=i % 4, sticky="nsew", padx=4, pady=4)
            grid.columnconfigure(i % 4, weight=1)
            tk.Label(card, text=f"関節 {i} の電源", bg=CARD, fg=MUTED).pack(anchor="w", padx=10, pady=(8, 2))
            labs = {}
            for key, title, col in (("v", "電圧", VOLT_COLOR), ("a", "電流", AMP_COLOR), ("w", "電力", WATT_COLOR)):
                r = tk.Frame(card, bg=CARD)
                r.pack(fill="x", padx=10, pady=2)
                tk.Label(r, text=title, bg=CARD, fg=MUTED).pack(side="left")
                # 等幅＋固定幅。電圧・電流・電力の桁が変わっても行幅が動かない
                lab = _value_label(r, col, MONO_LG)
                lab.pack(side="right")
                labs[key] = lab
            self.ina_labs.append(labs)
        self.plot_pwr = LinePlot(self.tab_pwr, "電力 [W]", 0, 40, "W")
        self.plot_v = LinePlot(self.tab_pwr, "電圧 [V]", 0, 16, "V")
        for i in range(INA_CHS):
            col = INA_PLOT_COLORS[i % len(INA_PLOT_COLORS)]
            self.plot_pwr.add_series(f"w{i}", col)
            self.plot_v.add_series(f"v{i}", col)
        self.plot_pwr.pack(fill="both", expand=True, padx=8, pady=6)
        self.plot_v.pack(fill="both", expand=True, padx=8, pady=6)

    def _build_time(self) -> None:
        self.time_labs: dict[str, tk.Label] = {}
        card = tk.Frame(self.tab_time, bg=CARD)
        card.pack(fill="x", padx=8, pady=6)
        for key, title in (("period", "周期"), ("loop", "ループ"), ("sense", "センサ"), ("jitter", "ジッタ"), ("i2c", "I2C累計"), ("servo", "8Servos")):
            r = tk.Frame(card, bg=CARD)
            r.pack(side="left", padx=12, pady=8)
            tk.Label(r, text=title, bg=CARD, fg=MUTED).pack()
            # 各列の数値幅を固定し、周期が変わっても列が左右に揺れないようにする
            lab = _value_label(r, PERIOD_COLOR, MONO_MD, anchor="center")
            lab.pack()
            self.time_labs[key] = lab
        self.plot_time = LinePlot(self.tab_time, "時間 [ms]  灰点線＝50ms", 0, 80, "ms")
        self.plot_time.add_series("period", PERIOD_COLOR)
        self.plot_time.add_series("loop", CMD_COLOR)
        self.plot_time.add_series("sense", AS_COLOR)
        self.plot_time.add_guide(TARGET_MS, MUTED)
        self.plot_time.pack(fill="both", expand=True, padx=8, pady=4)

    def _build_evt(self) -> None:
        row = tk.Frame(self.tab_evt, bg=BG)
        row.pack(fill="x", padx=8, pady=6)
        tk.Button(row, text="記録開始", command=self._start_log, bg=GOOD, fg=TEXT, relief="flat").pack(side="left")
        tk.Button(row, text="記録停止", command=self._stop_log, bg=CARD_HI, fg=TEXT, relief="flat").pack(
            side="left", padx=6
        )
        self.log_state = tk.Label(row, text="記録オフ", bg=BG, fg=MUTED)
        self.log_state.pack(side="left", padx=8)
        self.evt_text = tk.Text(
            self.tab_evt, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
            font=("Consolas", 9), wrap="none", height=18,
        )
        self.evt_text.pack(fill="both", expand=True, padx=8, pady=4)

    # ----- ポート / セッション -----
    def _refresh_ports(self) -> None:
        found = list_ports()
        self.port_list.delete(0, "end")
        for dev, desc in found:
            label = self.names.get(dev, "")
            extra = f"  [{label}]" if label else ""
            mark = " ●" if dev in self.sessions and self.sessions[dev].connected else ""
            self.port_list.insert("end", f"{dev}{extra}  {desc}{mark}")
        self._ports_raw = [p[0] for p in found]
        if self.current and self.current in self._ports_raw:
            idx = self._ports_raw.index(self.current)
            self.port_list.selection_set(idx)
        self.after(2500, self._refresh_ports)

    def _sel_port(self) -> str | None:
        sel = self.port_list.curselection()
        if not sel:
            return self.current
        idx = int(sel[0])
        if 0 <= idx < len(self._ports_raw):
            return self._ports_raw[idx]
        return self.current

    def _on_select_port(self, _evt: object = None) -> None:
        port = self._sel_port()
        if port:
            self.current = port
            self.name_var.set(self.names.get(port, ""))
            self._sync_detail()

    def _sess(self) -> AtomSession | None:
        if self.current is None:
            return None
        return self.sessions.get(self.current)

    def _ensure(self, port: str) -> AtomSession:
        if port not in self.sessions:
            s = AtomSession(port)
            s.name = self.names.get(port, "")
            self.sessions[port] = s
        return self.sessions[port]

    def _connect_sel(self) -> None:
        port = self._sel_port()
        if not port:
            return
        self.current = port
        self._ensure(port).connect()

    def _disconnect_sel(self) -> None:
        s = self._sess()
        if s:
            s.disconnect()

    def _connect_all(self) -> None:
        """Espressif(303A) の COM だけ開く。机の USB ハブ向け。"""
        for p in serial.tools.list_ports.comports():
            if "303A" not in (p.hwid or ""):
                continue
            s = self._ensure(p.device)
            if not s.connected:
                s.connect()

    def _save_name(self) -> None:
        port = self._sel_port()
        if not port:
            return
        self.names[port] = self.name_var.get().strip()
        save_names(self.names)
        if port in self.sessions:
            self.sessions[port].name = self.names[port]

    def _identify(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if s:
            s.send(proto.cmd_identify())

    def _scan(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if s:
            s.send(proto.cmd_scan())

    def _prof_get(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if s:
            s.send(proto.cmd_prof_get())

    def _prof_default(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if s:
            s.send(proto.cmd_prof_default())

    @staticmethod
    def _parse_int_field(text: str) -> int:
        text = text.strip().lower()
        if text.startswith("0x"):
            return int(text, 16)
        return int(text)

    def _routes_from_form(self) -> list[JointRoute] | None:
        routes: list[JointRoute] = []
        try:
            for row in self.prof_vars:
                routes.append(
                    JointRoute(
                        enc_hub=self._parse_int_field(row["enc_hub"].get()),
                        enc_ch=self._parse_int_field(row["enc_ch"].get()),
                        enc_addr=self._parse_int_field(row["enc_addr"].get()),
                        act_hub=self._parse_int_field(row["act_hub"].get()),
                        act_ch=self._parse_int_field(row["act_ch"].get()),
                        act_addr=self._parse_int_field(row["act_addr"].get()),
                        servo_ch=self._parse_int_field(row["servo_ch"].get()),
                        ina_hub=self._parse_int_field(row["ina_hub"].get()),
                        ina_ch=self._parse_int_field(row["ina_ch"].get()),
                        ina_addr=self._parse_int_field(row["ina_addr"].get()),
                    )
                )
        except ValueError as exc:
            messagebox.showerror("プロファイル", f"数値の形式が不正です: {exc}")
            return None
        return routes

    def _prof_put(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        routes = self._routes_from_form()
        if routes is None:
            return
        s.routes = routes
        s.send(proto.cmd_prof_put([route_tuple(r) for r in routes]))
        s.note("プロファイル送信")

    def _prof_from_scan(self) -> None:
        """スキャン結果の AS5600 を関節 0.. に仮割当（Hub CH 順）。サーボは手前 ch=i。"""
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        as_nodes = [n for n in s.nodes if n.kind == "as5600"]
        as_nodes.sort(key=lambda n: (n.hub, n.ch))
        if not as_nodes:
            messagebox.showinfo("プロファイル", "AS5600 がスキャン結果にありません。先に SCAN してください。")
            return
        routes = default_routes()
        for i, n in enumerate(as_nodes[:JOINTS]):
            if n.hub == "root":
                hub, ch = 0, -1
            else:
                try:
                    hub = int(str(n.hub), 16)
                except ValueError:
                    hub = 0x70
                ch = n.ch
            try:
                addr = int(str(n.addr), 0) if str(n.addr).lower().startswith("0x") else int(str(n.addr), 16)
            except ValueError:
                addr = 0x36
            routes[i] = JointRoute(
                enc_hub=hub,
                enc_ch=ch,
                enc_addr=addr,
                act_hub=0,
                act_ch=-1,
                act_addr=0x25,
                servo_ch=i,
                ina_hub=routes[i].ina_hub,
                ina_ch=routes[i].ina_ch,
                ina_addr=routes[i].ina_addr,
            )
        ina_nodes = [n for n in s.nodes if n.kind == "ina226"]
        ina_nodes.sort(key=lambda n: (n.hub, n.ch))
        for i, n in enumerate(ina_nodes[:JOINTS]):
            ih, ic, ia = scan_node_path(n)
            routes[i].ina_hub = ih
            routes[i].ina_ch = ic
            routes[i].ina_addr = ia
        s.routes = routes
        self._fill_prof_form(routes)
        s.note(
            f"SCANから仮割当  AS5600 {min(len(as_nodes), JOINTS)} 軸  "
            f"INA {min(len(ina_nodes), JOINTS)} 台"
        )

    def _fill_prof_form(self, routes: list[JointRoute]) -> None:
        self._syncing = True
        try:
            for i, r in enumerate(routes[:JOINTS]):
                row = self.prof_vars[i]
                row["enc_hub"].set(f"0x{r.enc_hub:02X}" if r.enc_hub else "0")
                row["enc_ch"].set(str(r.enc_ch))
                row["enc_addr"].set(f"0x{r.enc_addr:02X}")
                row["act_hub"].set(f"0x{r.act_hub:02X}" if r.act_hub else "0")
                row["act_ch"].set(str(r.act_ch))
                row["act_addr"].set(f"0x{r.act_addr:02X}")
                row["servo_ch"].set(str(r.servo_ch))
                row["ina_hub"].set(f"0x{r.ina_hub:02X}" if r.ina_hub else "0")
                row["ina_ch"].set(str(r.ina_ch))
                row["ina_addr"].set(f"0x{r.ina_addr:02X}" if r.ina_addr else "0")
        finally:
            self._syncing = False
        self._prof_sig = route_sig(routes)

    def _on_mode(self, _evt: object = None) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if s:
            s.send(proto.cmd_mode(self.mode_var.get() == "robot"))

    def _toggle_out(self, panel: int) -> None:
        if self._syncing or self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        j = self._panel_joint(panel)
        on = 1 if self.out_vars[j].get() else 0
        s.send(proto.cmd_out(j, bool(on)))
        if on:
            s.send(proto.cmd_joint(j, float(self.cmd_vars[j].get())))
        else:
            # PWM オフならランダムも止める
            if j < len(self.rand_vars):
                self.rand_vars[j].set(False)

    def _toggle_random(self, panel: int) -> None:
        """軸ごとのランダム ON/OFF。ON 時はすぐ次ターゲットを選ぶ。"""
        if self._pc_locked():
            return
        j = self._panel_joint(panel)
        if self.rand_vars[j].get():
            if not self.out_vars[j].get():
                self.out_vars[j].set(True)
                self._toggle_out(panel)
            self._rand_until[j] = 0.0
            s = self._sess()
            if s:
                s.note(f"関節{j} ランダム ON")
        else:
            s = self._sess()
            if s:
                s.note(f"関節{j} ランダム OFF")

    def _rand_settings(self) -> tuple[float, float, float, float, float]:
        """@return (min_deg, max_deg, hold_min_s, hold_max_s, min_jump)"""
        try:
            lo = float(self.rand_min_var.get())
            hi = float(self.rand_max_var.get())
            h0 = float(self.rand_hold_min_var.get())
            h1 = float(self.rand_hold_max_var.get())
            jump = float(self.rand_jump_var.get())
        except (tk.TclError, ValueError):
            return RAND_MIN_DEG, RAND_MAX_DEG, RAND_HOLD_MIN_S, RAND_HOLD_MAX_S, RAND_MIN_JUMP_DEG
        if hi < lo:
            lo, hi = hi, lo
        lo = max(40.0, min(230.0, lo))
        hi = max(40.0, min(230.0, hi))
        if h1 < h0:
            h0, h1 = h1, h0
        h0 = max(0.1, h0)
        h1 = max(h0, h1)
        jump = max(0.0, jump)
        return lo, hi, h0, h1, jump

    def _next_random_target(self, current: float) -> float:
        lo, hi, _h0, _h1, jump = self._rand_settings()
        if hi - lo < 1.0:
            return (lo + hi) * 0.5
        target = current
        for _ in range(12):
            target = random.uniform(lo, hi)
            if abs(target - current) >= min(jump, (hi - lo) * 0.5):
                break
        return target

    def _update_random(self) -> None:
        """保持時間が切れた軸に新しい #CMD を送る（PC 側ランダム）。"""
        s = self._sess()
        if not s or not s.connected:
            return
        now = time.time()
        _lo, _hi, hold_min, hold_max, _jump = self._rand_settings()
        for i in range(JOINTS):
            if i >= len(self.rand_vars) or not self.rand_vars[i].get():
                continue
            if not self.out_vars[i].get():
                continue
            if now < self._rand_until[i]:
                continue
            cur = float(self.cmd_vars[i].get())
            tgt = self._next_random_target(cur)
            hold = random.uniform(hold_min, hold_max)
            self._rand_until[i] = now + hold
            self._rand_target[i] = tgt
            self._syncing = True
            try:
                self.cmd_vars[i].set(round(tgt, 1))
            finally:
                self._syncing = False
            s.send(proto.cmd_joint(i, tgt))

    def _cmd_drag(self, panel: int) -> None:
        if self._syncing or self._pc_locked():
            return
        j = self._panel_joint(panel)
        # 手動操作したらその軸のランダムを止める
        if j < len(self.rand_vars) and self.rand_vars[j].get():
            self.rand_vars[j].set(False)
        now = time.time()
        if now - self._last_cmd_t[j] < 0.08:
            return
        self._last_cmd_t[j] = now
        s = self._sess()
        if s and self.out_vars[j].get():
            s.send(proto.cmd_joint(j, float(self.cmd_vars[j].get())))

    def _hold_all(self) -> None:
        for s in self.sessions.values():
            s.send(proto.cmd_hold())
        for v in self.out_vars:
            v.set(False)
        for v in self.rand_vars:
            v.set(False)

    def _probe(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        sel = self.tree.selection()
        if not sel:
            s.send(proto.cmd_scan())
            return
        iid = sel[0]
        # values stored as hub|ch|addr
        tags = self.tree.item(iid, "tags")
        if not tags:
            return
        meta = tags[0]
        hub, ch, addr = meta.split("|")
        if hub == "root":
            try:
                a = int(str(addr), 0) if str(addr).lower().startswith("0x") else int(str(addr), 16)
            except ValueError:
                a = 0x36
            s.send(proto.cmd_probe_root(a))
        else:
            try:
                hub_n = int(str(hub), 16)
            except ValueError:
                hub_n = 0x70
            s.send(proto.cmd_probe_hub(hub_n, int(ch)))

    def _tree_selected_node(self, s: AtomSession) -> ScanNode | None:
        sel = self.tree.selection()
        if not sel:
            return None
        tags = self.tree.item(sel[0], "tags")
        if not tags:
            return None
        hub, ch, addr = str(tags[0]).split("|")
        for n in s.nodes:
            if n.hub == hub and str(n.ch) == str(ch) and n.addr == addr:
                return n
        return None

    def _send_routes(self, s: AtomSession, routes: list[JointRoute], note: str) -> None:
        s.routes = routes
        s.send(proto.cmd_prof_put([route_tuple(r) for r in routes]))
        self._fill_prof_form(routes)
        self._ina_ui_sig = None
        self._refresh_ina_combos(s)
        s.note(note)

    def _assign_ina_from_tree(self) -> None:
        """トポロジで選んだ INA226 を指定関節の電源監視にする。"""
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        n = self._tree_selected_node(s)
        if n is None or n.kind != "ina226":
            messagebox.showinfo("INA", "トポロジで INA226 ノードを選んでください。")
            return
        joint = int(self.topo_ina_joint.get())
        if joint < 0 or joint >= JOINTS:
            return
        if joint >= len(s.routes):
            messagebox.showinfo("INA", f"このボードのプロファイルは関節 0〜{max(0, len(s.routes) - 1)} までです。")
            return
        hub, ch, addr = scan_node_path(n)
        routes = list(s.routes)
        while len(routes) < JOINTS:
            routes.append(default_routes()[len(routes)])
        routes[joint].ina_hub = hub
        routes[joint].ina_ch = ch
        routes[joint].ina_addr = addr
        self._send_routes(s, routes, f"INA 関節{joint} ← {ina_label(hub, ch, addr)}")

    def _clear_ina_from_tree(self) -> None:
        if self._pc_locked():
            return
        s = self._sess()
        if not s:
            return
        joint = int(self.topo_ina_joint.get())
        if joint < 0 or joint >= JOINTS:
            return
        if joint >= len(s.routes):
            messagebox.showinfo("INA", f"このボードのプロファイルは関節 0〜{max(0, len(s.routes) - 1)} までです。")
            return
        routes = list(s.routes)
        while len(routes) < JOINTS:
            routes.append(default_routes()[len(routes)])
        routes[joint].ina_hub = 0
        routes[joint].ina_ch = -1
        routes[joint].ina_addr = 0
        self._send_routes(s, routes, f"INA 関節{joint} を未割当")

    def _ina_option_list(self, s: AtomSession) -> list[str]:
        opts = ["なし"]
        seen: set[str] = set()
        for n in s.nodes:
            if n.kind != "ina226":
                continue
            hub, ch, addr = scan_node_path(n)
            lab = ina_label(hub, ch, addr)
            if lab not in seen:
                opts.append(lab)
                seen.add(lab)
        for r in s.routes[:JOINTS]:
            lab = ina_label(r.ina_hub, r.ina_ch, r.ina_addr)
            if lab not in seen:
                opts.append(lab)
                seen.add(lab)
        return opts

    def _refresh_ina_combos(self, s: AtomSession) -> None:
        if self._syncing or not getattr(self, "ina_combos", None):
            return
        opts = self._ina_option_list(s)
        self._syncing = True
        try:
            for p in range(len(self.ina_combos)):
                j = self._panel_joint(p)
                self.ina_combos[p]["values"] = opts
                if j >= len(s.routes):
                    self.ina_sel_vars[p].set("なし")
                    continue
                want = ina_label(s.routes[j].ina_hub, s.routes[j].ina_ch, s.routes[j].ina_addr)
                if want not in opts:
                    opts2 = list(opts) + [want]
                    self.ina_combos[p]["values"] = opts2
                self.ina_sel_vars[p].set(want)
        finally:
            self._syncing = False

    def _on_ina_combo(self, panel: int) -> None:
        if self._syncing or self._pc_locked():
            return
        s = self._sess()
        j = self._panel_joint(panel)
        if not s or j >= len(s.routes):
            return
        parsed = parse_ina_label(self.ina_sel_vars[panel].get())
        if parsed is None:
            return
        hub, ch, addr = parsed
        routes = list(s.routes)
        routes[j].ina_hub = hub
        routes[j].ina_ch = ch
        routes[j].ina_addr = addr
        self._send_routes(s, routes, f"INA 関節{j} ← {ina_label(hub, ch, addr)}")

    def _toggle_auto(self) -> None:
        if self._pc_locked():
            return
        if self._auto_scan.get():
            self._auto_loop()
        elif self._scan_job is not None:
            self.after_cancel(self._scan_job)
            self._scan_job = None

    def _auto_loop(self) -> None:
        if self._auto_scan.get():
            s = self._sess()
            if s and s.connected:
                s.send(proto.cmd_scan())
            self._scan_job = self.after(5000, self._auto_loop)

    def _start_log(self) -> None:
        s = self._sess()
        if not s:
            return
        path = filedialog.asksaveasfilename(
            title="記録ファイル",
            defaultextension=".log",
            initialfile=f"lab_{s.port}_{time.strftime('%Y%m%d_%H%M%S')}.log",
        )
        if path:
            s.start_log(Path(path))
            self.log_state.configure(text=f"記録中  {path}", fg=GOOD)

    def _stop_log(self) -> None:
        s = self._sess()
        if s:
            s.stop_log()
        self.log_state.configure(text="記録オフ", fg=MUTED)

    def _on_close(self) -> None:
        for s in self.sessions.values():
            s.disconnect()
        self.destroy()

    # ----- 描画 -----
    def _tick(self) -> None:
        for s in self.sessions.values():
            s.pump()
            f = s.last_frame
            if f is not None:
                try:
                    lim = float(self._amp_limit.get())
                except (tk.TclError, ValueError):
                    lim = 8.0
                assigned = [i for i, r in enumerate(s.routes[:JOINTS]) if r.ina_addr]
                over = bool(assigned) and any(
                    f.ina_ok[i] and a is not None and abs(a) > lim
                    for i, a in enumerate(f.amp)
                    if i < len(s.routes) and s.routes[i].ina_addr
                )
                if over and not getattr(s, "amp_tripped", False):
                    s.amp_tripped = True
                    s.send(proto.cmd_hold())
                    for v in self.rand_vars:
                        v.set(False)
                    for v in self.out_vars:
                        v.set(False)
                    s.note(f"PC監視 電流が {lim} A を超えた")
                elif not over:
                    s.amp_tripped = False
        self._update_random()
        self._sync_detail()
        self._draw_cards()
        self._m5_publish_tick()
        self.after(50, self._tick)

    def _card_text(self, s: AtomSession) -> tuple[str, str, str]:
        """カード表示用 (text, bg, fg)。"""
        bg = CARD_HI if time.time() < s.flash_until else CARD
        fg = GOOD if s.connected else BAD
        title = s.name or s.port
        f = s.last_frame
        extra = f"  {f.mode}  out={f.out_mask}" if f else ""
        text = f"{title}\n{s.port}  {'接続' if s.connected else '切断'}{extra}"
        return text, bg, fg

    def _draw_cards(self) -> None:
        # 毎 tick の destroy/再生成は Tk を詰まらせ #S キュー溢れの原因になるので、構成が変わったときだけ作る。
        ports = tuple(self.sessions.keys())
        if getattr(self, "_card_ports", None) != ports or not getattr(self, "_card_labs", None):
            for w in self.card_host.winfo_children():
                w.destroy()
            self._card_labs = {}
            self._card_ports = ports
            for port, s in self.sessions.items():
                text, bg, fg = self._card_text(s)
                lab = tk.Label(
                    self.card_host,
                    text=text,
                    bg=bg, fg=fg, justify="left", anchor="w",
                )
                lab.pack(fill="x", pady=3)
                lab.bind("<Button-1>", lambda _e, p=port: self._click_card(p))
                self._card_labs[port] = lab
            return
        for port, s in self.sessions.items():
            lab = self._card_labs.get(port)
            if lab is None:
                continue
            text, bg, fg = self._card_text(s)
            lab.configure(text=text, bg=bg, fg=fg)

    def _click_card(self, port: str) -> None:
        self.current = port
        if port in getattr(self, "_ports_raw", []):
            self.port_list.selection_clear(0, "end")
            self.port_list.selection_set(self._ports_raw.index(port))
        self.name_var.set(self.names.get(port, ""))
        self._sync_detail()

    def _sync_detail(self) -> None:
        s = self._sess()
        if s is None:
            self.sel_label.configure(text="未選択")
            self.hello_label.configure(text="")
            return
        title = s.name or s.port
        self.sel_label.configure(text=title)
        self.hello_label.configure(text=s.hello)
        if s.mode in ("lab", "robot") and self.mode_var.get() != s.mode:
            self.mode_var.set(s.mode)
        self._fill_tree(s)
        if self._prof_sig != route_sig(s.routes):
            self._fill_prof_form(s.routes)
        ina_sig = (tuple(self._ina_option_list(s)), route_sig(s.routes))
        if ina_sig != getattr(self, "_ina_ui_sig", None):
            self._ina_ui_sig = ina_sig
            self._refresh_ina_combos(s)
        f = s.last_frame
        if f is not None:
            self._apply_frame(s, f)
        if getattr(self, "cal_status_lab", None) is not None:
            ui_sig = (s.cal_status, s.map_ch, len(s.map_points))
            if ui_sig != getattr(self, "_cal_ui_sig", None):
                self._cal_ui_sig = ui_sig
                self._refresh_cal_labels(s)
        sig = s.events[0] if s.events else ""
        if sig != self._evt_sig:
            self._evt_sig = sig
            lines = "\n".join(s.events)
            self.evt_text.delete("1.0", "end")
            self.evt_text.insert("1.0", lines)

    def _fill_tree(self, s: AtomSession) -> None:
        sig = (s.port, tuple((n.hub, n.ch, n.addr, n.kind, n.mag, n.agc) for n in s.nodes))
        if sig == self._tree_sig:
            return
        self._tree_sig = sig
        self.tree.delete(*self.tree.get_children())
        root_id = self.tree.insert("", "end", text=f"{s.port}  Grove I2C", values=("", "", ""))
        hubs: dict[str, str] = {}
        for n in s.nodes:
            mag = MAG_LABEL.get(n.mag, str(n.mag)) if n.kind == "as5600" else ""
            agc = "" if n.agc == 255 else str(n.agc)
            tag = f"{n.hub}|{n.ch}|{n.addr}"
            if n.hub == "root":
                if n.kind == "pahub":
                    hid = self.tree.insert(
                        root_id, "end", text=f"PaHub {n.addr}",
                        values=(n.kind, "", ""), tags=(tag,),
                    )
                    hubs[n.addr.replace("0x", "").replace("0X", "").upper()] = hid
                    hubs[n.addr] = hid
                else:
                    self.tree.insert(
                        root_id, "end", text=n.addr,
                        values=(n.kind, mag, agc), tags=(tag,),
                    )
            else:
                parent = hubs.get(n.hub.upper()) or hubs.get(n.hub) or root_id
                self.tree.insert(
                    parent, "end", text=f"CH{n.ch}  {n.addr}",
                    values=(n.kind, mag, agc), tags=(tag,),
                )
        self.tree.item(root_id, open=True)
        for hid in hubs.values():
            try:
                self.tree.item(hid, open=True)
            except tk.TclError:
                pass

    def _fill_joint_panel(self, f: Frame, panel: int) -> None:
        """1 枚の関節パネルを、選択中の論理関節のテレメトリで更新する。"""
        if panel < 0 or panel >= len(self.joint_labs):
            return
        j = self._panel_joint(panel)
        labs = self.joint_labs[panel]
        cmd = _at(f.cmd, j)
        raw = _at(f.raw, j)
        unw = _at(f.unwrap, j)
        corr = _at(f.corr, j)
        mag = _at(f.mag, j, 255)
        agc = _at(f.agc, j, 255)
        volt = _at(f.volt, j)
        amp = _at(f.amp, j)
        watt = _at(f.watt, j)
        labs["cmd"].configure(text=_fmt(cmd, "°"))
        labs["raw"].configure(text=_fmt(raw, "°"))
        labs["unw"].configure(text=_fmt(unw, "°"))
        labs["corr"].configure(text=_fmt(corr, "°"), fg=CORR_COLOR)
        labs["mag"].configure(text=MAG_LABEL.get(mag, str(mag)), fg=mag_color(mag))
        labs["agc"].configure(text="—" if agc == 255 else f"{agc:3d}")
        labs["v"].configure(text=_fmt(volt, "V"))
        labs["a"].configure(text=_fmt(amp, "A"))
        labs["w"].configure(text=_fmt(watt, "W"))

    def _apply_frame(self, s: AtomSession, f: Frame) -> None:
        # out_vars はユーザー操作の意図。#S の out_mask で上書きするとチェックが勝手に外れる。
        for p in range(len(self.joint_labs)):
            self._fill_joint_panel(f, p)

        # チェック ON なのにボード側がオフなら、短周期で再送（校正終了・取りこぼし対策）
        now = time.time()
        if now - self._last_out_reassert >= 0.4:
            resent = False
            for i in range(JOINTS):
                if self.out_vars[i].get() and not (f.out_mask & (1 << i)):
                    s.send(proto.cmd_out(i, True))
                    s.send(proto.cmd_joint(i, float(self.cmd_vars[i].get())))
                    resent = True
            if resent:
                self._last_out_reassert = now

        for i in range(INA_CHS):
            self.ina_labs[i]["v"].configure(text=_fmt(f.volt[i], "V"))
            self.ina_labs[i]["a"].configure(text=_fmt(f.amp[i], "A"))
            self.ina_labs[i]["w"].configure(text=_fmt(f.watt[i], "W"))
        self.time_labs["period"].configure(text=_fmt_ms(f.period_us))
        self.time_labs["loop"].configure(text=_fmt_ms(f.loop_us))
        self.time_labs["sense"].configure(text=_fmt_ms(f.sense_us))
        self.time_labs["jitter"].configure(text=_fmt_ms(f.jitter_us))
        self.time_labs["i2c"].configure(text=f"{f.i2c_err:6d}")
        self.time_labs["servo"].configure(text="OK" if f.servo_ok else "なし", fg=GOOD if f.servo_ok else BAD)

        if self._plot_port != s.port:
            self.plot_ang.clear()
            self.plot_pwr.clear()
            self.plot_v.clear()
            self.plot_time.clear()
            self._plot_port = s.port
            self._last_plot_seq = None

        if self._last_plot_seq != (s.port, f.seq):
            self._last_plot_seq = (s.port, f.seq)
            j = self._plot_joint_index()
            self.plot_ang.push("cmd", f.t, _at(f.cmd, j))
            self.plot_ang.push("raw", f.t, _at(f.raw, j))
            self.plot_ang.push("unw", f.t, _at(f.unwrap, j))
            self.plot_ang.push("corr", f.t, _at(f.corr, j))
            self.plot_ang.push("v", f.t, _at(f.volt, j))
            self.plot_ang.push("a", f.t, _at(f.amp, j))
            self.plot_ang.push("w", f.t, _at(f.watt, j))
            for i in range(INA_CHS):
                self.plot_pwr.push(f"w{i}", f.t, _at(f.watt, i))
                self.plot_v.push(f"v{i}", f.t, _at(f.volt, i))
            self.plot_time.push("period", f.t, f.period_us / 1000.0)
            self.plot_time.push("loop", f.t, f.loop_us / 1000.0)
            self.plot_time.push("sense", f.t, f.sense_us / 1000.0)

        if now - self._last_plot < PLOT_INTERVAL_S:
            return
        self._last_plot = now
        self.plot_ang.redraw()
        self.plot_pwr.redraw()
        self.plot_v.redraw()
        self.plot_time.redraw()


def _at(xs: list, i: int, default=None):
    """範囲外なら default。テレメトリが 2 軸でも関節 2〜7 を選んで壊れないようにする。"""
    if 0 <= i < len(xs):
        return xs[i]
    return default


def _fmt(v: float | None, unit: str) -> str:
    """数値を固定桁で整形する。等幅フォントと組み合わせて表示位置を固定する。"""
    if v is None:
        return f"— {unit}"
    # 整数部最大4桁 + 小数2桁。unwrap が 360° を超えても幅が変わらない
    return f"{v:8.2f} {unit}"


def _fmt_ms(us: int) -> str:
    """マイクロ秒を固定桁のミリ秒表示にする（符号付きジッタも幅が変わらない）。"""
    return f"{us / 1000.0:7.1f} ms"


def main() -> None:
    app = LabApp()
    app.mainloop()


if __name__ == "__main__":
    main()
