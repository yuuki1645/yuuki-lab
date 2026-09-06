#!/usr/bin/env python3
"""
rt-usb ファーム専用のリアルタイムモニタ（atom-rt）。

USB シリアルで 20 Hz スナップショットを受け、
グラフと数値を同じ画面に出す（Wi-Fi は使わない）。
servo_monitor.py とは別アプリ。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import queue
import threading
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox, ttk

from cal_map_io import load_map, save_map
import rt_usb_proto as proto

import serial
import serial.tools.list_ports

# ---------------------------------------------------------------------------
# 見た目
# ---------------------------------------------------------------------------
BG = "#0e1318"
CARD = "#17202a"
CARD_HI = "#1f2a36"
TEXT = "#e8eef4"
MUTED = "#8b9bb0"
CMD_COLOR = "#ff9f43"
AS_COLOR = "#54a0ff"
UNWRAP_COLOR = "#1dd1a1"
PERIOD_COLOR = "#f5f6fa"
LOOP_COLOR = "#ff9f43"
SENSE_COLOR = "#54a0ff"
STATE_COLOR = "#a29bfe"
POLICY_COLOR = "#fd79a8"
ACT_COLOR = "#00cec9"
JITTER_COLOR = "#ffeaa7"
VOLT_COLOR = "#feca57"
AMP_COLOR = "#00d2d3"
WATT_COLOR = "#ff6b81"
GOOD = "#10ac84"
BAD = "#ee5253"
GRID = "#2a3644"
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
TARGET_HZ = 20.0
TARGET_US = 50_000.0
HISTORY_SEC = 20.0
JOINTS = 8
INA_CHS = proto.INA_CHS
INA_PLOT_COLORS = (
    "#ff6b81",
    "#00d2d3",
    "#feca57",
    "#e67e22",
    "#5f27cd",
    "#10ac84",
    "#54a0ff",
    "#c8d6e5",
)
# 数値は毎フレーム、グラフはこれ以上速く描かない（Tk Canvas 対策）
PLOT_INTERVAL_S = 0.10
# 1 本あたりの描画点数上限。多いときは間引く
PLOT_MAX_POINTS = 160


@dataclass
class Frame:
    """ボード 1 周期分。"""

    t: float
    seq: int
    period_us: int
    loop_us: int
    sense_us: int
    state_us: int
    policy_us: int
    act_us: int
    jitter_us: int
    overrun: bool
    cmd: list[float | None] = field(default_factory=lambda: [None] * JOINTS)
    raw: list[float | None] = field(default_factory=lambda: [None] * JOINTS)
    unwrap: list[float | None] = field(default_factory=lambda: [None] * JOINTS)
    corr: list[float | None] = field(default_factory=lambda: [None] * JOINTS)
    as_ok: list[bool] = field(default_factory=lambda: [False] * JOINTS)
    volt: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    amp: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    watt: list[float | None] = field(default_factory=lambda: [None] * INA_CHS)
    ina_ok: list[bool] = field(default_factory=lambda: [False] * INA_CHS)
    # USB フレームにその行が実際に含まれていたか（欠けとセンサNGを分ける）
    j_got: list[bool] = field(default_factory=lambda: [False] * JOINTS)
    p_got: list[bool] = field(default_factory=lambda: [False] * INA_CHS)


def frame_from_telem(t: proto.Telemetry) -> Frame:
    """バイナリテレメトリをモニタ用 Frame にする。"""
    f = Frame(
        t=time.time(),
        seq=t.seq,
        period_us=t.period_us,
        loop_us=t.loop_us,
        sense_us=t.sense_us,
        state_us=t.state_us,
        policy_us=t.policy_us,
        act_us=t.act_us,
        jitter_us=t.jitter_us,
        overrun=t.overrun,
        cmd=list(t.cmd),
        raw=list(t.raw),
        unwrap=list(t.unwrap),
        corr=list(t.corr),
        as_ok=list(t.as_ok),
        volt=list(t.volt),
        amp=list(t.amp),
        watt=list(t.watt),
        ina_ok=list(t.ina_ok),
        j_got=[True] * JOINTS,
        p_got=[True] * INA_CHS,
    )
    return f


def list_ports() -> list[str]:
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=lambda p: (0 if "303A" in (p.hwid or "") else 1, p.device))
    return [p.device for p in ports]


class UsbWorker:
    """USB を裏スレッドで読む。Thread 継承はしない（3.13 対策）。"""

    def __init__(self, port: str, out: queue.Queue) -> None:
        self.port = port
        self.out = out
        self._stop = threading.Event()
        self._tx: queue.Queue[bytes] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        # GUI が切り替える。送受信ログ用（GIL で bool 代入は十分）
        self.wire_log = False

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        """停止して COM を確実に閉じる（再接続の PermissionError 防止）。"""
        self._stop.set()
        self._thread.join(timeout=2.0)

    def send(self, data: bytes) -> None:
        self._tx.put(data)

    def _emit_wire(self, prefix: str, text: str) -> None:
        """解釈済みの送受信を GUI へ。キューが厚いときは捨てる。"""
        if not self.wire_log:
            return
        if self.out.qsize() < 80:
            self.out.put(("wire", (prefix, text)))

    def _try_log(self, text: str) -> None:
        if self.out.qsize() < 40:
            self.out.put(("log", text))

    def _run(self) -> None:
        try:
            ser = serial.Serial(self.port, BAUD, timeout=0.05)
        except serial.SerialException as exc:
            self.out.put(("error", str(exc)))
            return
        self.out.put(("status", f"接続 {self.port}"))
        parser = proto.FrameParser()
        map_acc: list[tuple[float, float]] = []
        map_ch = 0
        try:
            while not self._stop.is_set():
                sent = False
                try:
                    msg = self._tx.get_nowait()
                    ser.write(msg)
                    ser.flush()
                    self._emit_wire("<", proto.format_tx(msg))
                    sent = True
                except queue.Empty:
                    pass

                try:
                    waiting = ser.in_waiting
                    if waiting > 0:
                        chunk = ser.read(waiting)
                    elif sent:
                        time.sleep(0.010)
                        continue
                    else:
                        chunk = ser.read(256)
                except serial.SerialException as exc:
                    self.out.put(("error", str(exc)))
                    break

                if not chunk:
                    continue
                for msg_type, payload in parser.feed(chunk):
                    self._emit_wire(">", proto.format_rx(msg_type, payload))
                    self._feed_frame(msg_type, payload)
                    if msg_type == proto.MSG_MAP_CHUNK:
                        c = proto.decode_map_chunk(payload)
                        if c is None:
                            continue
                        if c.start == 0:
                            map_acc = list(c.points)
                            map_ch = c.ch
                        else:
                            map_acc.extend(c.points)
                        if c.total == 0 or (c.start + len(c.points) >= c.total):
                            self.out.put(("map_done", (map_ch, list(map_acc))))
                            map_acc = []
        finally:
            try:
                ser.close()
            except serial.SerialException:
                pass
            self.out.put(("status", "切断"))

    def _feed_frame(self, msg_type: int, payload: bytes) -> None:
        if msg_type == proto.MSG_TELEMETRY:
            t = proto.decode_telemetry(payload)
            if t is None:
                self._try_log("テレメトリ（形式不正）")
                return
            frame = frame_from_telem(t)
            if self.out.qsize() < 24:
                self.out.put(("frame", frame))
            else:
                self._try_log(f"GUIキュー満杯  seq={frame.seq} を破棄")
            return
        if msg_type in (proto.MSG_MAP_OK, proto.MSG_MAP_ERR):
            self.out.put(("log", proto.format_rx(msg_type, payload)))
            return
        if msg_type == proto.MSG_MAP_CHUNK:
            return
        if msg_type in (proto.MSG_HELLO, proto.MSG_MODE, proto.MSG_EVT_OC, proto.MSG_EVT_BTN):
            self.out.put(("log", proto.format_rx(msg_type, payload)))


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
        self.guides: list[tuple[float, str]] = []
        self._resize_job: str | None = None
        # リサイズ中に毎回全描画すると重いので遅延する
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, _event: tk.Event) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self.redraw)

    def add_series(self, name: str, color: str) -> None:
        self.series[name] = deque()
        self.colors[name] = color
        self.latest[name] = None

    def add_guide(self, y: float, color: str) -> None:
        self.guides.append((y, color))

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
        pad_l, pad_r, pad_t, pad_b = 52, 118, 26, 16
        self.create_text(12, 12, anchor="w", text=self.title, fill=MUTED, font=("Segoe UI", 10))

        # 凡例＋今の数値
        ly = 12
        for name, color in self.colors.items():
            val = self.latest.get(name)
            text = f"{name}  —" if val is None else f"{name}  {val:.1f}{self.yunit}"
            self.create_text(w - 8, ly, anchor="e", text=text, fill=color, font=("Segoe UI", 9))
            ly += 14

        ymin, ymax = self.ymin, self.ymax
        for tick in (ymin, (ymin + ymax) / 2, ymax):
            y = pad_t + (1 - (tick - ymin) / (ymax - ymin)) * (h - pad_t - pad_b)
            self.create_line(pad_l, y, w - pad_r, y, fill=GRID)
            label = f"{tick:.0f}" if abs(tick) >= 10 else f"{tick:.1f}"
            self.create_text(pad_l - 6, y, text=label, fill=MUTED, font=("Segoe UI", 8), anchor="e")

        for gy, color in self.guides:
            if ymin <= gy <= ymax:
                y = pad_t + (1 - (gy - ymin) / (ymax - ymin)) * (h - pad_t - pad_b)
                self.create_line(pad_l, y, w - pad_r, y, fill=color, dash=(4, 3))

        now = time.time()
        t0 = now - HISTORY_SEC
        t1 = now

        def xy(t: float, v: float) -> tuple[float, float]:
            x = pad_l + ((t - t0) / max(0.1, t1 - t0)) * (w - pad_l - pad_r)
            y = pad_t + (1 - (v - ymin) / (ymax - ymin)) * (h - pad_t - pad_b)
            return x, y

        for name, hist in self.series.items():
            n = len(hist)
            if n < 2:
                continue
            # 点が多いときは等間隔に間引き、最後の点は必ず残す
            step = 1 if n <= PLOT_MAX_POINTS else max(1, n // PLOT_MAX_POINTS)
            pts: list[float] = []
            for i in range(0, n, step):
                x, y = xy(*hist[i])
                pts.extend((x, y))
            if (n - 1) % step != 0:
                x, y = xy(*hist[-1])
                pts.extend((x, y))
            if len(pts) >= 4:
                # smooth はスプライン計算が重いので使わない
                self.create_line(*pts, fill=self.colors[name], width=2)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("rt-usb  リアルタイムモニタ  20Hz")
        self.geometry("1280x780")
        self.minsize(1040, 640)
        self.configure(bg=BG)

        self.q: queue.Queue = queue.Queue()
        self.worker: UsbWorker | None = None
        self.history: deque[Frame] = deque(maxlen=int(HISTORY_SEC * TARGET_HZ * 2))
        self.overrun_count = 0
        self._last_seq: int | None = None
        self._dropped = 0
        self._last_plot = 0.0
        self.map_points: list[tuple[float, float]] = []
        self.map_ch = 0
        self._map_save_after = False
        # anomaly = 欠測だけ / wire = 送受信すべて
        self.log_mode = tk.StringVar(value="anomaly")

        self._build()
        self.after(50, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=8)

        tk.Label(top, text="COM", bg=BG, fg=MUTED).pack(side="left")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=12, state="readonly")
        self.port_box.pack(side="left", padx=6)
        tk.Button(top, text="更新", command=self._refresh_ports, bg=CARD_HI, fg=TEXT, relief="flat", padx=8).pack(
            side="left"
        )
        tk.Button(top, text="接続", command=self._connect, bg=CMD_COLOR, fg="#1b1208", relief="flat", padx=12).pack(
            side="left", padx=6
        )
        tk.Button(top, text="切断", command=self._disconnect, bg=CARD_HI, fg=TEXT, relief="flat", padx=10).pack(
            side="left"
        )
        tk.Label(top, text="軸", bg=BG, fg=MUTED).pack(side="left", padx=(16, 2))
        self.map_ch_var = tk.IntVar(value=0)
        ttk.Spinbox(top, from_=0, to=1, textvariable=self.map_ch_var, width=3).pack(side="left")
        tk.Button(
            top, text="マップDL", command=self.download_map, bg=UNWRAP_COLOR, fg="#082018", relief="flat", padx=8
        ).pack(side="left", padx=6)
        tk.Button(
            top, text="マップUL", command=self.upload_map, bg=CMD_COLOR, fg="#1b1208", relief="flat", padx=8
        ).pack(side="left")
        self.status = tk.Label(top, text="未接続  （rt-usb を USB でつないでください）", bg=BG, fg=MUTED)
        self.status.pack(side="left", padx=16)
        self._refresh_ports()

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # 左: タイミング数値
        left = tk.Frame(body, bg=CARD, width=280)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        tk.Label(left, text="制御ループ時間", bg=CARD, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=12, pady=(10, 4))
        self.time_labels: dict[str, tk.Label] = {}
        for key, title, color in (
            ("period", "周期 t_period", PERIOD_COLOR),
            ("loop", "実行 t_loop", LOOP_COLOR),
            ("sense", "センサ t_sense", SENSE_COLOR),
            ("state", "状態 t_state", STATE_COLOR),
            ("policy", "政策 t_policy", POLICY_COLOR),
            ("act", "関節 t_act", ACT_COLOR),
            ("jitter", "ジッタ", JITTER_COLOR),
            ("over", "超過 / 欠落", BAD),
        ):
            row = tk.Frame(left, bg=CARD)
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=title, bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
            lab = _value_label(row, color, MONO_MD)
            lab.pack(side="right")
            self.time_labels[key] = lab

        tk.Label(left, text="直近統計（20秒）", bg=CARD, fg=MUTED, font=("Segoe UI", 10)).pack(
            anchor="w", padx=12, pady=(16, 4)
        )
        self.stat = tk.Label(
            left,
            text="period  —\nloop    —\njitter  —",
            bg=CARD,
            fg=TEXT,
            font=("Consolas", 11),
            justify="left",
            anchor="w",
        )
        self.stat.pack(fill="x", padx=12, pady=(0, 10))

        # 中央: グラフ + 下の調査ログ
        mid = tk.Frame(body, bg=BG)
        mid.pack(side="left", fill="both", expand=True)

        log_wrap = tk.Frame(mid, bg=CARD, height=168)
        log_wrap.pack(side="bottom", fill="x")
        log_wrap.pack_propagate(False)
        log_head = tk.Frame(log_wrap, bg=CARD)
        log_head.pack(fill="x", padx=8, pady=(6, 2))
        self.log_title = tk.Label(
            log_head,
            text="調査ログ（欠行 / センサNG / フレーム欠け）",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
        )
        self.log_title.pack(side="left")
        tk.Radiobutton(
            log_head,
            text="欠測のみ",
            variable=self.log_mode,
            value="anomaly",
            command=self._on_log_mode,
            bg=CARD,
            fg=TEXT,
            selectcolor=CARD_HI,
            activebackground=CARD,
            activeforeground=TEXT,
            font=("Segoe UI", 9),
        ).pack(side="right", padx=(8, 0))
        tk.Radiobutton(
            log_head,
            text="送受信すべて",
            variable=self.log_mode,
            value="wire",
            command=self._on_log_mode,
            bg=CARD,
            fg=TEXT,
            selectcolor=CARD_HI,
            activebackground=CARD,
            activeforeground=TEXT,
            font=("Segoe UI", 9),
        ).pack(side="right")
        log_inner = tk.Frame(log_wrap, bg=CARD)
        log_inner.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        scroll = tk.Scrollbar(log_inner)
        scroll.pack(side="right", fill="y")
        self.log = tk.Text(
            log_inner,
            height=8,
            bg=CARD_HI,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 9),
            wrap="none",
            yscrollcommand=scroll.set,
        )
        self.log.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.log.yview)
        self.log.tag_configure("rx", foreground=UNWRAP_COLOR)
        self.log.tag_configure("tx", foreground=CMD_COLOR)
        self.log.insert(
            "end",
            "欠測・壊れた行・周期飛びだけ出します。数値は欠けても前回値を維持します。\n"
            "「送受信すべて」で > 受信 / < 送信 を全部出します。\n",
        )
        self.log.configure(state="disabled")

        plots = tk.Frame(mid, bg=BG)
        plots.pack(side="top", fill="both", expand=True)

        self.plot_time = LinePlot(plots, "時間 [ms]   灰点線＝目標 50ms", 0.0, 80.0, " ms")
        self.plot_time.add_series("period", PERIOD_COLOR)
        self.plot_time.add_series("loop", LOOP_COLOR)
        self.plot_time.add_series("sense", SENSE_COLOR)
        self.plot_time.add_guide(50.0, MUTED)
        self.plot_time.pack(fill="both", expand=True, pady=(0, 6))

        self.plot_jitter = LinePlot(plots, "ジッタ [ms]   目標周期からのずれ", -15.0, 15.0, " ms")
        self.plot_jitter.add_series("jitter", JITTER_COLOR)
        self.plot_jitter.add_guide(0.0, MUTED)
        self.plot_jitter.pack(fill="both", expand=True, pady=(0, 6))

        self.plot_ang = LinePlot(plots, "関節角 [°]   橙＝指令  青＝生  緑＝unwrap  白＝補正", 0.0, 360.0, "°")
        self.plot_ang.add_series("cmd0", CMD_COLOR)
        self.plot_ang.add_series("raw0", AS_COLOR)
        self.plot_ang.add_series("unw0", UNWRAP_COLOR)
        self.plot_ang.add_series("corr0", PERIOD_COLOR)
        self.plot_ang.add_series("cmd1", "#c56b1b")
        self.plot_ang.add_series("raw1", "#2d6dad")
        self.plot_ang.add_series("unw1", "#0e8f70")
        self.plot_ang.pack(fill="both", expand=True, pady=(0, 6))

        self.plot_pwr = LinePlot(plots, "電力 [W]   関節ごと INA226", 0.0, 40.0, " W")
        for i in range(INA_CHS):
            self.plot_pwr.add_series(f"w{i}", INA_PLOT_COLORS[i % len(INA_PLOT_COLORS)])
        self.plot_pwr.pack(fill="both", expand=True)

        # 右: センサ数値
        right = tk.Frame(body, bg=BG, width=300)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        self.joint_box = []
        for i in range(JOINTS):
            card = tk.Frame(right, bg=CARD)
            card.pack(fill="x", pady=(0, 8))
            tk.Label(card, text=f"関節 {i}", bg=CARD, fg=MUTED, font=("Segoe UI", 10)).pack(
                anchor="w", padx=12, pady=(8, 2)
            )
            labs = {}
            for key, title, color in (
                ("cmd", "指令", CMD_COLOR),
                ("raw", "AS5600 生", AS_COLOR),
                ("unw", "unwrap", UNWRAP_COLOR),
                ("corr", "補正後", PERIOD_COLOR),
                ("ok", "センサ", MUTED),
            ):
                row = tk.Frame(card, bg=CARD)
                row.pack(fill="x", padx=12, pady=2)
                tk.Label(row, text=title, bg=CARD, fg=MUTED).pack(side="left")
                lab = _value_label(row, color, MONO_LG)
                lab.pack(side="right")
                labs[key] = lab
            self.joint_box.append(labs)

        self.ina_box = []
        ina_grid = tk.Frame(right, bg=BG)
        ina_grid.pack(fill="x", pady=(0, 8))
        for i in range(INA_CHS):
            card = tk.Frame(ina_grid, bg=CARD)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=2, pady=2)
            ina_grid.columnconfigure(i % 2, weight=1)
            tk.Label(card, text=f"関節 {i} INA", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(
                anchor="w", padx=8, pady=(4, 0)
            )
            labs = {}
            for key, title, color in (
                ("v", "電圧", VOLT_COLOR),
                ("a", "電流", AMP_COLOR),
                ("w", "電力", WATT_COLOR),
            ):
                row = tk.Frame(card, bg=CARD)
                row.pack(fill="x", padx=8, pady=1)
                tk.Label(row, text=title, bg=CARD, fg=MUTED).pack(side="left")
                lab = _value_label(row, color, MONO)
                lab.pack(side="right")
                labs[key] = lab
            self.ina_box.append(labs)

    def download_map(self) -> None:
        """ボードから指定軸のマップを受け、JSON に保存する。"""
        if self.worker is None:
            messagebox.showwarning("マップ", "先に接続してください")
            return
        self._map_save_after = True
        ch = int(self.map_ch_var.get())
        self.worker.send(proto.cmd_map_get(ch))
        self._append_log(f"マップ取得要求  ch{ch}")

    def _save_map_dialog(self) -> None:
        if len(self.map_points) < 2:
            messagebox.showwarning("マップ", "ボードにマップがありません")
            return
        path = filedialog.asksaveasfilename(
            title="校正マップを保存",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("すべて", "*.*")],
            initialfile=f"cal_map_ch{self.map_ch}.json",
        )
        if not path:
            return
        save_map(path, self.map_ch, self.map_points)
        self._append_log(f"マップ保存  {path}  {len(self.map_points)}点")

    def upload_map(self) -> None:
        """JSON を読み、ボードの NVS へ送る。"""
        if self.worker is None:
            messagebox.showwarning("マップ", "先に接続してください")
            return
        path = filedialog.askopenfilename(
            title="校正マップを開く",
            filetypes=[("JSON", "*.json"), ("すべて", "*.*")],
        )
        if not path:
            return
        try:
            file_ch, points = load_map(path)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("マップ", str(exc))
            return
        ch = int(self.map_ch_var.get())
        if file_ch != ch:
            if not messagebox.askyesno("マップ", f"ファイルは ch{file_ch} です。ch{ch} として送りますか？"):
                return
        if len(points) < 8:
            messagebox.showwarning("マップ", "点が少なすぎます")
            return
        for fr in proto.cmd_map_chunks(ch, points):
            self.worker.send(fr)
        self.map_points = points
        self.map_ch = ch
        self._append_log(f"マップ送信開始  ch{ch}  {len(points)}点  → ボード保存完了を待つ")

    def _refresh_ports(self) -> None:
        ports = list_ports()
        self.port_box["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _connect(self) -> None:
        """接続。既に開いているときは一旦閉じてから開き直す。"""
        self._disconnect()
        port = self.port_var.get()
        if not port:
            self.status.configure(text="COM がありません", fg=BAD)
            return
        # 前スレッドの close() が終わるまで待つ（COM 占有対策）
        time.sleep(0.15)
        self.worker = UsbWorker(port, self.q)
        self.worker.wire_log = self.log_mode.get() == "wire"
        self.worker.start()
        # 新ファームは Lab（PWM オフ）が既定。このモニタは従来どおり動かす
        self.worker.send(proto.cmd_mode(True))

    def _disconnect(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None

    def _on_close(self) -> None:
        self._disconnect()
        self.destroy()

    def _pump(self) -> None:
        """USBキューを吸い、数値とグラフを更新する。例外でも次回を予約する。"""
        latest: Frame | None = None
        try:
            try:
                while True:
                    kind, payload = self.q.get_nowait()
                    if kind == "status":
                        self.status.configure(text=str(payload), fg=GOOD)
                        self._append_log(str(payload))
                    elif kind == "error":
                        self.status.configure(text=str(payload), fg=BAD)
                        self._append_log(f"ERROR  {payload}")
                    elif kind == "log":
                        self._append_log(str(payload))
                    elif kind == "wire":
                        prefix, body = payload
                        tag = "tx" if prefix == "<" else "rx"
                        self._append_log(f"{prefix} {body}", tag=tag)
                    elif kind == "map_done":
                        if isinstance(payload, tuple) and len(payload) == 2:
                            self.map_ch = int(payload[0])
                            self.map_points = list(payload[1])
                            self._append_log(f"マップ受信  ch{self.map_ch}  {len(self.map_points)}点")
                            if self._map_save_after:
                                self._map_save_after = False
                                self._save_map_dialog()
                    elif kind == "frame":
                        # 溜まっていても履歴とカウンタは全部取り込む
                        self._ingest(payload)
                        latest = payload
            except queue.Empty:
                pass
            if latest is not None:
                # 表示は最新 1 枚だけ。グラフは 10Hz までに抑える
                self._apply_labels(latest)
                now = time.time()
                if (now - self._last_plot) >= PLOT_INTERVAL_S:
                    self._last_plot = now
                    self._redraw_plots()
                    self._apply_stats()
        except Exception as exc:
            try:
                self._append_log(f"GUI更新エラー  {exc}")
            except Exception:
                pass
        self.after(50, self._pump)

    def _ingest(self, f: Frame) -> None:
        """履歴と欠落カウントだけ更新する（Canvas は触らない）。"""
        if self._last_seq is not None and f.seq > self._last_seq + 1:
            gap = f.seq - self._last_seq - 1
            self._dropped += gap
            self._append_log(f"seq {f.seq}  欠落 {gap} 周期（USB破棄 or キュー溢れ）")
        self._last_seq = f.seq
        if f.overrun:
            self.overrun_count += 1
            self._append_log(f"seq {f.seq}  OVER  t_loop={f.loop_us}us")
        self.history.append(f)
        self._log_anomalies(f)

        def ms(us: int) -> float:
            return us / 1000.0

        self.plot_time.push("period", f.t, ms(f.period_us))
        self.plot_time.push("loop", f.t, ms(f.loop_us))
        self.plot_time.push("sense", f.t, ms(f.sense_us))
        self.plot_jitter.push("jitter", f.t, ms(f.jitter_us))
        self.plot_ang.push("cmd0", f.t, f.cmd[0])
        self.plot_ang.push("raw0", f.t, f.raw[0])
        self.plot_ang.push("unw0", f.t, f.unwrap[0])
        self.plot_ang.push("corr0", f.t, f.corr[0])
        self.plot_ang.push("cmd1", f.t, f.cmd[1])
        self.plot_ang.push("raw1", f.t, f.raw[1])
        self.plot_ang.push("unw1", f.t, f.unwrap[1])
        for i in range(INA_CHS):
            self.plot_pwr.push(f"w{i}", f.t, f.watt[i] if i < len(f.watt) else None)

    def _on_log_mode(self) -> None:
        """ログ表示を切り替える。線への出し入れは Worker 側で見る。"""
        wire = self.log_mode.get() == "wire"
        if self.worker is not None:
            self.worker.wire_log = wire
        if wire:
            self.log_title.configure(text="調査ログ（> 受信   < 送信）")
            self._append_log("ログモード  送受信すべて  >受信  <送信")
        else:
            self.log_title.configure(text="調査ログ（欠行 / センサNG / フレーム欠け）")
            self._append_log("ログモード  欠測のみ")

    def _append_log(self, text: str, tag: str | None = None) -> None:
        """調査ログへ1行足す。多すぎたら古い行を捨てる。"""
        stamp = time.strftime("%H:%M:%S")
        line = f"{stamp}  {text}\n"
        self.log.configure(state="normal")
        start = self.log.index("end-1c")
        self.log.insert("end", line)
        if tag:
            self.log.tag_add(tag, start, "end-1c")
        # 送受信モードは行が多いので少し多めに残す
        keep = 800 if self.log_mode.get() == "wire" else 400
        extra = int(self.log.index("end-1c").split(".")[0]) - keep
        if extra > 0:
            self.log.delete("1.0", f"{extra + 1}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _log_anomalies(self, f: Frame) -> None:
        """右パネルが --- / なし になる原因を分類して出す。"""
        bits: list[str] = []
        for i in range(JOINTS):
            if not f.as_ok[i]:
                bits.append(f"関節{i}=センサNG")
            elif f.raw[i] is None:
                bits.append(f"関節{i}=欠測")
        for i in range(INA_CHS):
            if f.ina_ok[i] and f.volt[i] is None:
                bits.append(f"INA{i}=欠測")
        if bits:
            self._append_log(f"seq {f.seq}  " + "  ".join(bits))

    def _redraw_plots(self) -> None:
        self.plot_time.redraw()
        self.plot_jitter.redraw()
        self.plot_ang.redraw()
        self.plot_pwr.redraw()

    def _apply_stats(self) -> None:
        if not self.history:
            return
        periods = [x.period_us / 1000.0 for x in self.history]
        loops = [x.loop_us / 1000.0 for x in self.history]
        jitters = [x.jitter_us / 1000.0 for x in self.history]
        n = len(periods)
        self.stat.configure(
            text=(
                f"period  min {min(periods):5.2f}  max {max(periods):5.2f}  "
                f"avg {sum(periods)/n:5.2f} ms\n"
                f"loop    min {min(loops):5.2f}  max {max(loops):5.2f}  "
                f"avg {sum(loops)/n:5.2f} ms\n"
                f"jitter  min {min(jitters):+5.2f}  max {max(jitters):+5.2f}  "
                f"avg {sum(jitters)/n:+5.2f} ms"
            )
        )

    def _apply_labels(self, f: Frame) -> None:
        """右側・左側の数値だけ更新する。"""

        def ms(us: int) -> float:
            return us / 1000.0

        self.time_labels["period"].configure(text=f"{ms(f.period_us):6.2f} ms")
        self.time_labels["loop"].configure(text=f"{ms(f.loop_us):6.2f} ms")
        self.time_labels["sense"].configure(text=f"{ms(f.sense_us):6.2f} ms")
        self.time_labels["state"].configure(text=f"{ms(f.state_us):6.2f} ms")
        self.time_labels["policy"].configure(text=f"{ms(f.policy_us):6.2f} ms")
        self.time_labels["act"].configure(text=f"{ms(f.act_us):6.2f} ms")
        jcol = BAD if abs(f.jitter_us) > 8000 else JITTER_COLOR
        self.time_labels["jitter"].configure(text=f"{ms(f.jitter_us):+6.2f} ms", fg=jcol)
        self.time_labels["over"].configure(text=f"{self.overrun_count:4d} / {self._dropped:4d}")

        for i, labs in enumerate(self.joint_box):
            # 欠けた周期は --- にせず、直前の表示を残す
            if f.cmd[i] is not None:
                labs["cmd"].configure(text=f"{f.cmd[i]:6.2f} °")
            if f.raw[i] is not None:
                labs["raw"].configure(text=f"{f.raw[i]:6.2f} °")
            if f.unwrap[i] is not None:
                labs["unw"].configure(text=f"{f.unwrap[i]:6.2f} °")
            if f.corr[i] is not None:
                labs["corr"].configure(text=f"{f.corr[i]:6.2f} °")
            if f.j_got[i]:
                if f.as_ok[i]:
                    labs["ok"].configure(text="OK", fg=GOOD)
                else:
                    labs["ok"].configure(text="なし", fg=BAD)

        for i, labs in enumerate(self.ina_box):
            if f.volt[i] is not None:
                labs["v"].configure(text=f"{f.volt[i]:6.2f} V")
            if f.amp[i] is not None:
                labs["a"].configure(text=f"{f.amp[i]:6.3f} A")
            if f.watt[i] is not None:
                labs["w"].configure(text=f"{f.watt[i]:6.3f} W")

        hz = 1e6 / f.period_us if f.period_us > 0 else 0.0
        flag = "  OVER" if f.overrun else ""
        self.status.configure(text=f"seq {f.seq}   {hz:.1f} Hz{flag}", fg=BAD if f.overrun else GOOD)


if __name__ == "__main__":
    App().mainloop()
