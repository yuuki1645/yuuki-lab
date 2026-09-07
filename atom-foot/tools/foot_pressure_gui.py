#!/usr/bin/env python3
"""
足裏圧力 GUI（ATOMS3 Lite マスター USB）。

robotics-hub の足裏四隅マップ（つま先が上、ヒート、圧力中心、合計 kg）を
tkinter で再現し、通信は yuuki-lab-robot-side と同じバイナリ USB フレーム。

  pip install -r tools/requirements.txt
  python tools/foot_pressure_gui.py
"""

from __future__ import annotations

import colorsys
import math
import queue
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))

import serial
import serial.tools.list_ports

import df9_force
import usb_proto as proto

# ---------------------------------------------------------------------------
# 見た目（lab_debug / robotics-hub に寄せたダークテーマ）
# ---------------------------------------------------------------------------
BG = "#0e1318"
CARD = "#17202a"
CARD_HI = "#1f2a36"
TEXT = "#e8eef4"
MUTED = "#8b9bb0"
GOOD = "#10ac84"
WARN = "#feca57"
BAD = "#ee5253"
GRID = "#2a3644"
PLATE = "#0c1224"
SOLE_BORDER = "#b4c8ff"

BAUD = 115200
HISTORY_SEC = 20.0
PLOT_INTERVAL_S = 0.10
PLOT_MAX_POINTS = 160
STALE_SEC = 2.5
FORCE_MAX_KG = df9_force.FORCE_MAX_KG

CORNER_DEFS = (
    ("top_left", "左上", "G5", -1.0, -1.0),
    ("top_right", "右上", "G6", 1.0, -1.0),
    ("bottom_left", "左下", "G8", -1.0, 1.0),
    ("bottom_right", "右下", "G7", 1.0, 1.0),
)
# テレメトリ mv の並びは TL, TR, BR, BL
MV_INDEX = {
    "top_left": 0,
    "top_right": 1,
    "bottom_right": 2,
    "bottom_left": 3,
}


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def force_heat_hex(ratio: float) -> str:
    """低: シアン → 中: 黄 → 高: 赤。Hub の forceHeatHsl と同じ曲線。"""
    t = clamp01(ratio)
    hue = 190 - t * 2 * 145 if t < 0.5 else 45 - (t - 0.5) * 2 * 37
    sat = 0.78 + t * 0.12
    light = 0.52 - t * 0.08
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, light, sat)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def mix_hex(a: str, b: str, t: float) -> str:
    t = clamp01(t)

    def ch(h: str, i: int) -> int:
        return int(h[1 + i * 2 : 3 + i * 2], 16)

    rgb = [int(ch(a, i) * (1 - t) + ch(b, i) * t) for i in range(3)]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def format_kg(kg: float | None) -> str:
    if kg is None or not math.isfinite(kg):
        return "—.—"
    if kg < 0.001:
        return "0.000"
    return f"{kg:.3f}"


def list_ports() -> list[tuple[str, str]]:
    """(COM, 説明) ATOMS3(303A) を先頭に。"""
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=lambda p: (0 if "303A" in (p.hwid or "") else 1, p.device))
    return [(p.device, p.description or "") for p in ports]


@dataclass
class CornerSample:
    force_kg: float
    voltage_v: float
    rs_ohm: float
    mv: int


@dataclass
class Frame:
    t: float
    seq: int
    period_us: int
    loop_us: int
    i2c_us: int
    slave_ok: bool
    overrun: bool
    i2c_err: int
    corners: dict[str, CornerSample] = field(default_factory=dict)
    total_kg: float = 0.0


def frame_from_telem(t: proto.Telemetry) -> Frame:
    """ミリボルトを DF9-40 力に換算して GUI 用 Frame にする。"""
    corners: dict[str, CornerSample] = {}
    total = 0.0
    for key, idx in MV_INDEX.items():
        mv = t.mv[idx] if t.slave_ok else 0
        voltage = mv / 1000.0
        rs, force = df9_force.voltage_to_force_kg(voltage)
        if not t.slave_ok:
            force = 0.0
        corners[key] = CornerSample(force_kg=force, voltage_v=voltage, rs_ohm=rs, mv=mv)
        total += force
    return Frame(
        t=time.time(),
        seq=t.seq,
        period_us=t.period_us,
        loop_us=t.loop_us,
        i2c_us=t.i2c_us,
        slave_ok=t.slave_ok,
        overrun=t.overrun,
        i2c_err=t.i2c_err,
        corners=corners,
        total_kg=total,
    )


class UsbWorker:
    """USB を裏スレッドで読む。Thread 継承はしない（3.13 対策）。"""

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
        if self.out.qsize() < 200:
            self.out.put((kind, payload))

    def _run(self) -> None:
        try:
            ser = serial.Serial(self.port, BAUD, timeout=0.05)
        except serial.SerialException as exc:
            self._put("error", str(exc))
            return
        self._put("status", f"接続 {self.port}")
        parser = proto.FrameParser()
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
        if msg_type in (proto.MSG_IDENTIFY_OK, proto.MSG_EVT_BTN):
            self._put("log", proto.format_rx(msg_type, payload))


class LinePlot(tk.Canvas):
    """時系列の折れ線。右側に今の数値を出す。"""

    def __init__(self, parent: tk.Widget, title: str, ymin: float, ymax: float, yunit: str) -> None:
        super().__init__(parent, bg=CARD, highlightthickness=0)
        self.title = title
        self.ymin = ymin
        self.ymax = ymax
        self.yunit = yunit
        self.series: dict[str, deque[tuple[float, float]]] = {}
        self.colors: dict[str, str] = {}
        self.latest: dict[str, float | None] = {}
        self._resize_job: str | None = None
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, _event: tk.Event) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self.redraw)

    def add_series(self, name: str, color: str) -> None:
        self.series[name] = deque()
        self.colors[name] = color
        self.latest[name] = None

    def push(self, name: str, t: float, value: float | None) -> None:
        hist = self.series[name]
        if value is None:
            self.latest[name] = None
            return
        hist.append((t, value))
        cutoff = t - HISTORY_SEC
        while hist and hist[0][0] < cutoff:
            hist.popleft()
        self.latest[name] = value

    def redraw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 40 or h < 40:
            return
        pad_l, pad_r, pad_t, pad_b = 48, 110, 26, 16
        self.create_text(12, 12, anchor="w", text=self.title, fill=MUTED, font=("Segoe UI", 10))

        ly = 12
        for name, color in self.colors.items():
            val = self.latest.get(name)
            text = f"{name}  —" if val is None else f"{name}  {val:.3f}{self.yunit}"
            self.create_text(w - 8, ly, anchor="e", text=text, fill=color, font=("Segoe UI", 9))
            ly += 14

        ymin, ymax = self.ymin, self.ymax
        for tick in (ymin, (ymin + ymax) / 2, ymax):
            y = pad_t + (1 - (tick - ymin) / max(1e-6, ymax - ymin)) * (h - pad_t - pad_b)
            self.create_line(pad_l, y, w - pad_r, y, fill=GRID)
            self.create_text(
                pad_l - 6, y, text=f"{tick:.1f}", fill=MUTED, font=("Segoe UI", 8), anchor="e"
            )

        now = time.time()
        t0 = now - HISTORY_SEC
        t1 = now

        def xy(t: float, v: float) -> tuple[float, float]:
            x = pad_l + ((t - t0) / max(0.1, t1 - t0)) * (w - pad_l - pad_r)
            y = pad_t + (1 - (v - ymin) / max(1e-6, ymax - ymin)) * (h - pad_t - pad_b)
            return x, y

        for name, hist in self.series.items():
            n = len(hist)
            if n < 2:
                continue
            step = 1 if n <= PLOT_MAX_POINTS else max(1, n // PLOT_MAX_POINTS)
            pts: list[float] = []
            for i in range(0, n, step):
                x, y = xy(hist[i][0], hist[i][1])
                pts.extend((x, y))
            if n - 1 not in range(0, n, step):
                x, y = xy(hist[-1][0], hist[-1][1])
                pts.extend((x, y))
            self.create_line(*pts, fill=self.colors[name], width=2, smooth=True)


class FootSoleMap(tk.Canvas):
    """足裏フレーム四隅のヒートマップ（Hub FootSolePressureMap 相当）。"""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, bg=BG, highlightthickness=0, width=340, height=460)
        self.display: dict[str, dict[str, float]] = {
            key: {"kg": 0.0, "ratio": 0.0} for key, *_ in CORNER_DEFS
        }
        self.display_total = 0.0
        self.frame: Frame | None = None
        self.connected = False
        self.stale_sec: float | None = None
        self.bind("<Configure>", lambda _e: self.redraw())

    def set_state(self, frame: Frame | None, connected: bool, stale_sec: float | None) -> None:
        self.frame = frame
        self.connected = connected
        self.stale_sec = stale_sec

    def tick_smooth(self) -> None:
        """表示値を目標へ滑らかに追従させる。"""
        idle = (not self.connected) or self.frame is None
        for key, *_ in CORNER_DEFS:
            target_kg = 0.0 if idle else self.frame.corners[key].force_kg
            target_ratio = clamp01(target_kg / FORCE_MAX_KG)
            cur = self.display[key]
            cur["kg"] += (target_kg - cur["kg"]) * 0.22
            cur["ratio"] += (target_ratio - cur["ratio"]) * 0.18
        t_target = 0.0 if idle else self.frame.total_kg
        if idle:
            self.display_total *= 0.85
        else:
            self.display_total += (t_target - self.display_total) * 0.22

    def _cop(self) -> tuple[float, float] | None:
        if self.frame is None:
            return None
        wx = wy = w = 0.0
        for key, _label, _pin, x, y in CORNER_DEFS:
            f = max(0.0, self.frame.corners[key].force_kg)
            if f < 0.02:
                continue
            wx += x * f
            wy += y * f
            w += f
        if w < 0.05:
            return None
        return wx / w, wy / w

    def redraw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 80 or h < 80:
            return

        idle = (not self.connected) or self.frame is None
        stale = self.stale_sec is not None and self.stale_sec > STALE_SEC

        self.create_text(w / 2, 18, text="つま先", fill=MUTED, font=("Segoe UI", 10), anchor="n")
        self.create_text(w / 2, h - 18, text="かかと", fill=MUTED, font=("Segoe UI", 10), anchor="s")

        left, top, right, bottom = 28, 42, w - 28, h - 42
        self.create_round_rect(left, top, right, bottom, 18, PLATE, SOLE_BORDER)

        pad_w = (right - left) * 0.38
        pad_h = (bottom - top) * 0.32
        positions = {
            "top_left": (left + 12, top + 18),
            "top_right": (right - 12 - pad_w, top + 18),
            "bottom_left": (left + 12, bottom - 18 - pad_h),
            "bottom_right": (right - 12 - pad_w, bottom - 18 - pad_h),
        }

        for key, label, pin, _x, _y in CORNER_DEFS:
            px, py = positions[key]
            d = self.display[key]
            heat = force_heat_hex(d["ratio"])
            fill = mix_hex(CARD, heat, 0.18 + d["ratio"] * 0.45)
            outline = mix_hex(SOLE_BORDER, heat, 0.35 + d["ratio"] * 0.4)
            self.create_round_rect(px, py, px + pad_w, py + pad_h, 12, fill, outline)
            self.create_text(
                px + pad_w / 2, py + 14, text=label, fill=TEXT, font=("Segoe UI", 10, "bold")
            )
            self.create_text(
                px + pad_w / 2, py + 30, text=pin, fill=MUTED, font=("Consolas", 9)
            )
            kg_text = "—" if idle else format_kg(d["kg"])
            self.create_text(
                px + pad_w / 2,
                py + pad_h / 2 + 4,
                text=kg_text,
                fill=heat if not idle else MUTED,
                font=("Segoe UI", 16, "bold"),
            )
            if not idle:
                self.create_text(
                    px + pad_w / 2 + 28, py + pad_h / 2 + 8, text="kg", fill=MUTED, font=("Segoe UI", 8)
                )
            bar_l, bar_r = px + pad_w * 0.12, px + pad_w * 0.88
            bar_y = py + pad_h - 12
            self.create_line(bar_l, bar_y, bar_r, bar_y, fill=GRID, width=4)
            self.create_line(
                bar_l,
                bar_y,
                bar_l + (bar_r - bar_l) * d["ratio"],
                bar_y,
                fill=heat,
                width=4,
            )

        cop = None if idle else self._cop()
        if cop is not None:
            cx = (left + right) / 2 + cop[0] * (right - left) * 0.28
            cy = (top + bottom) / 2 + cop[1] * (bottom - top) * 0.28
            self.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill="#f8fbff", outline="#0ea5e9", width=2)

        box_w, box_h = 96, 64
        bx = (left + right) / 2 - box_w / 2
        by = (top + bottom) / 2 - box_h / 2
        self.create_round_rect(bx, by, bx + box_w, by + box_h, 12, "#0a0e1e", SOLE_BORDER)
        self.create_text(bx + box_w / 2, by + 12, text="合計", fill=MUTED, font=("Segoe UI", 8))
        total_fill = TEXT if not stale else MUTED
        self.create_text(
            bx + box_w / 2,
            by + 32,
            text=format_kg(None if idle else self.display_total),
            fill=total_fill,
            font=("Segoe UI", 16, "bold"),
        )
        fresh = "—"
        if self.stale_sec is not None:
            fresh = "live" if self.stale_sec < 1 else f"{self.stale_sec:.1f} s"
        self.create_text(bx + box_w / 2, by + 50, text=fresh, fill=GOOD, font=("Consolas", 8))

    def create_round_rect(
        self, x1: float, y1: float, x2: float, y2: float, r: float, fill: str, outline: str
    ) -> None:
        """角丸矩形。Canvas に native が無いので多角形で近似する。"""
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        self.create_polygon(pts, smooth=True, fill=fill, outline=outline, width=2)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("足裏圧力  DF9-40 × ATOMS3 Lite")
        self.geometry("1180x720")
        self.configure(bg=BG)
        self.minsize(960, 620)

        self._q: queue.Queue = queue.Queue()
        self._worker: UsbWorker | None = None
        self._last_frame: Frame | None = None
        self._last_rx = 0.0
        self._connected = False
        self._status = "未接続"
        self._hello = ""
        self._last_plot = 0.0

        self._build_style()
        self._build_ui()
        self.after(50, self._pump)
        self.after(16, self._animate)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TCombobox", font=("Segoe UI", 10))

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=10)

        ttk.Label(top, text="COM").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, width=28, state="readonly")
        self.port_combo.pack(side="left", padx=8)
        ttk.Button(top, text="更新", command=self._refresh_ports).pack(side="left")
        ttk.Button(top, text="接続", command=self._connect).pack(side="left", padx=(12, 0))
        ttk.Button(top, text="切断", command=self._disconnect).pack(side="left", padx=6)
        ttk.Button(top, text="Identify", command=self._identify).pack(side="left")
        ttk.Button(top, text="Ping", command=self._ping).pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="未接続")
        ttk.Label(top, textvariable=self.status_var, style="Muted.TLabel").pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        left = ttk.Frame(body, style="Card.TFrame")
        left.pack(side="left", fill="both", expand=False, padx=(0, 10))
        ttk.Label(left, text="足裏圧力（DF9-40@2kg）", style="Card.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        self.sole = FootSoleMap(left)
        self.sole.pack(fill="both", expand=True, padx=8, pady=8)

        self.meta = tk.Text(
            left, height=6, bg=CARD_HI, fg=TEXT, relief="flat", font=("Consolas", 9),
            highlightthickness=0, wrap="none",
        )
        self.meta.pack(fill="x", padx=8, pady=(0, 10))
        self.meta.configure(state="disabled")

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.plot_force = LinePlot(right, "四隅の力", 0.0, FORCE_MAX_KG, " kg")
        self.plot_force.add_series("左上", "#54a0ff")
        self.plot_force.add_series("右上", "#1dd1a1")
        self.plot_force.add_series("右下", "#feca57")
        self.plot_force.add_series("左下", "#ff6b81")
        self.plot_force.add_series("合計", "#f5f6fa")
        self.plot_force.pack(fill="both", expand=True, pady=(0, 8))

        self.plot_v = LinePlot(right, "分圧電圧", 0.0, 3.3, " V")
        self.plot_v.add_series("左上", "#54a0ff")
        self.plot_v.add_series("右上", "#1dd1a1")
        self.plot_v.add_series("右下", "#feca57")
        self.plot_v.add_series("左下", "#ff6b81")
        self.plot_v.pack(fill="both", expand=True)

        self._refresh_ports()

    def _refresh_ports(self) -> None:
        ports = list_ports()
        labels = [f"{p}  {d}" for p, d in ports]
        self.port_combo["values"] = labels
        if labels and not self.port_var.get():
            self.port_combo.current(0)

    def _selected_port(self) -> str | None:
        raw = self.port_var.get().strip()
        if not raw:
            return None
        return raw.split()[0]

    def _connect(self) -> None:
        port = self._selected_port()
        if not port:
            self.status_var.set("COM を選んでください")
            return
        self._disconnect()
        self._worker = UsbWorker(port, self._q)
        self._worker.start()
        self.after(400, self._ping)

    def _disconnect(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
        self._connected = False
        self._last_frame = None
        self.status_var.set("未接続")

    def _ping(self) -> None:
        if self._worker is not None:
            self._worker.send(proto.cmd_ping())

    def _identify(self) -> None:
        if self._worker is not None:
            self._worker.send(proto.cmd_identify())

    def _on_close(self) -> None:
        self._disconnect()
        self.destroy()

    def _set_meta(self, lines: list[str]) -> None:
        self.meta.configure(state="normal")
        self.meta.delete("1.0", "end")
        self.meta.insert("1.0", "\n".join(lines))
        self.meta.configure(state="disabled")

    def _pump(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "frame":
                    self._last_frame = payload
                    self._last_rx = time.time()
                    self._connected = True
                    self._push_plots(payload)
                elif kind == "status":
                    self._status = str(payload)
                    self._connected = self._status.startswith("接続")
                    self.status_var.set(self._status)
                elif kind == "hello":
                    self._hello = str(payload)
                    self.status_var.set(self._hello)
                elif kind == "error":
                    self._connected = False
                    self.status_var.set(f"エラー  {payload}")
                elif kind == "log":
                    self.status_var.set(str(payload))
        except queue.Empty:
            pass

        stale = None
        if self._last_frame is not None:
            stale = time.time() - self._last_rx
        self.sole.set_state(self._last_frame, self._connected, stale)
        self._update_meta()
        self.after(50, self._pump)

    def _push_plots(self, frame: Frame) -> None:
        now = time.time()
        if now - self._last_plot < PLOT_INTERVAL_S:
            return
        self._last_plot = now
        names = {
            "top_left": "左上",
            "top_right": "右上",
            "bottom_right": "右下",
            "bottom_left": "左下",
        }
        for key, ja in names.items():
            c = frame.corners[key]
            self.plot_force.push(ja, frame.t, c.force_kg)
            self.plot_v.push(ja, frame.t, c.voltage_v)
        self.plot_force.push("合計", frame.t, frame.total_kg)
        self.plot_force.redraw()
        self.plot_v.redraw()

    def _update_meta(self) -> None:
        f = self._last_frame
        if f is None:
            self._set_meta(["サンプルなし"])
            return
        lines = [
            f"seq={f.seq}  slave={'OK' if f.slave_ok else 'NG'}  "
            f"overrun={'YES' if f.overrun else 'no'}  i2c_err={f.i2c_err}",
            f"period={f.period_us/1000:.1f} ms  loop={f.loop_us/1000:.2f} ms  "
            f"i2c={f.i2c_us/1000:.2f} ms",
        ]
        for key, label, pin, _x, _y in CORNER_DEFS:
            c = f.corners[key]
            lines.append(
                f"{label} ({pin})  {c.force_kg:6.3f} kg  {c.voltage_v:5.3f} V  "
                f"Rs={c.rs_ohm:,.0f} Ω  {c.mv} mV"
            )
        self._set_meta(lines)

    def _animate(self) -> None:
        self.sole.tick_smooth()
        self.sole.redraw()
        self.after(16, self._animate)


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
