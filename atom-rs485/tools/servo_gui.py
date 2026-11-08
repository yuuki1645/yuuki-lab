#!/usr/bin/env python3
"""
SM105BL の机上試験。ATOM S3R + ATOMIC RS485 ベースの USB CDC を開く。

ファーム（atom-rs485）が RS485 を話し、この GUI は行テキストで指示する。
接続してもトルクは入らない。トルク ON は、今の位置を目標にして保持させる。
目標が 0 のまま出力すると、中点付近から 0 カウントへ回るため。

起動:
    pip install -r tools/requirements.txt
    python tools/servo_gui.py

書き込みは atom-rs485 で pio run -t upload。この個体の can-leg は置き換わる。
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

import serial
import serial.tools.list_ports

BAUD = 115200
STREAM_HZ = 20
# 1 周 4096。1 カウントは 360/4096 度（約 0.0879°）。中点は 2048。
COUNTS_PER_REV = 4096
# これより大きい絶対移動は、押す前に確認する。150 kg·cm なので半周は遠すぎる。
CONFIRM_COUNTS = 512  # 45°

BG = "#0e1318"
CARD = "#17202a"
CARD_HI = "#1f2a36"
TEXT = "#e8eef4"
MUTED = "#8b9bb0"
GOOD = "#10ac84"
BAD = "#ee5253"
WARN = "#feca57"
ACCENT = "#54a0ff"
GRID = "#2a3644"
FONT = ("Yu Gothic UI", 10)
FONT_SM = ("Yu Gothic UI", 9)
MONO = ("Consolas", 12, "bold")
MONO_LG = ("Consolas", 20, "bold")

# アドレス 65。立っているビットが異常。
STATUS_BITS = (
    (1, "電圧"),
    (2, "磁気エンコーダ"),
    (4, "温度"),
    (8, "電流"),
    (32, "過負荷"),
)
# アドレス 18。速度の単位はビット2。
PHASE_SPEED_FINE = 0x04
TORQUE_NAME = {0: "切断", 1: "出力中", 2: "ダンパ"}
MODE_NAME = {0: "位置サーボ", 1: "定速", 2: "PWM開ループ", 3: "ステップ"}


def decode_bit15(raw: int) -> int:
    """ビット15が方向、下位15ビットが大きさ。位置と速度。"""
    if raw & 0x8000:
        return -(raw & 0x7FFF)
    return raw & 0x7FFF


def decode_bit10(raw: int) -> int:
    """ビット10が方向、下位10ビットが大きさ。負荷と PWM。1000 まで入る。"""
    sign = -1 if (raw & 0x0400) else 1
    return sign * (raw & 0x03FF)


def counts_from_deg(deg: float) -> int:
    return int(round(deg * COUNTS_PER_REV / 360.0))


def fmt_deg(counts: int) -> str:
    return f"{counts * 360.0 / COUNTS_PER_REV:+.2f}°"


def _self_check() -> None:
    """符号ビットの取り違えは軸を逆に動かす。起動時に既知の値だけ確認する。"""
    assert decode_bit15(2048) == 2048
    assert decode_bit15(0x8000 | 100) == -100
    assert decode_bit10(1000) == 1000
    assert decode_bit10(0x0400 | 100) == -100
    assert counts_from_deg(90) == 1024
    assert counts_from_deg(5) == 57


def is_atom_hwid(hwid: str | None) -> bool:
    return "303A" in (hwid or "")


def list_ports() -> list[tuple[str, str]]:
    """(COM, 表示)。Espressif VID 303A を先頭にする。"""
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=lambda p: (0 if is_atom_hwid(p.hwid) else 1, p.device))
    labeled = []
    for port in ports:
        mark = "ATOM " if is_atom_hwid(port.hwid) else ""
        desc = port.description or ""
        labeled.append((port.device, f"{mark}{port.device}  {desc}".strip()))
    return labeled


def open_atom_serial(port: str) -> serial.Serial:
    """DTR を立てると USB を開くたびに ATOM がリセットされる。立てない。"""
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = BAUD
    ser.timeout = 0.05
    ser.dsrdtr = False
    ser.rtscts = False
    ser.dtr = False
    ser.rts = False
    ser.open()
    ser.dtr = False
    ser.rts = False
    return ser


def _int_token(kv: dict[str, str], key: str) -> int | None:
    raw = kv.get(key)
    if raw is None:
        return None
    try:
        return int(raw, 10)
    except ValueError:
        return None


def parse_line(text: str) -> tuple[str, dict[str, str]]:
    """`@fb k=v ...` を (種別, 辞書) にする。@ が無ければ log。"""
    if not text.startswith("@"):
        return "log", {"text": text}
    parts = text.split()
    kind = parts[0][1:]
    kv: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        kv[key] = value
    return kind, kv


class ServoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SM105BL 試験  /  ATOM S3R + ATOMIC RS485")
        self.configure(bg=BG)
        self.minsize(1080, 760)
        self.geometry("1180x820")

        self._ports: list[tuple[str, str]] = []
        self.ser: serial.Serial | None = None
        self._tx_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue[tuple[str, dict[str, str]]] = queue.Queue()

        self.connected = False
        self.online = False
        self.armed = False
        self._stop_pending = False
        self._closing = False
        self._jog_buttons: list[tk.Button] = []
        self._phase = 0
        self._pos: int | None = None
        self._last_ok = 0.0
        self._fb_times: deque[float] = deque(maxlen=40)
        self._slider_ready = False

        self._hist_pos: deque[float] = deque(maxlen=200)
        self._hist_spd: deque[float] = deque(maxlen=200)
        self._hist_cur: deque[float] = deque(maxlen=200)
        self._hist_tmp: deque[float] = deque(maxlen=200)
        self._graph_dirty = False

        self._build()
        self._refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _event: self._torque_off())
        self.after(50, self._tick)

    # ------------------------------------------------------------------
    # 画面
    # ------------------------------------------------------------------

    def _build(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="ポート", bg=BG, fg=MUTED, font=FONT).pack(side="left")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=42, state="readonly")
        self.port_box.pack(side="left", padx=(6, 6))
        self._button(top, "更新", self._refresh_ports).pack(side="left")
        self.connect_btn = self._button(top, "接続", self._toggle_connect)
        self.connect_btn.pack(side="left", padx=(6, 12))
        tk.Label(top, text="ID", bg=BG, fg=MUTED, font=FONT).pack(side="left")
        self.id_var = tk.StringVar(value="1")
        tk.Entry(top, textvariable=self.id_var, width=4, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat").pack(
            side="left", padx=(4, 4)
        )
        self._button(top, "IDを使う", self._apply_id).pack(side="left", padx=(0, 12))
        self.link_var = tk.StringVar(value="未接続")
        self.link_label = tk.Label(top, textvariable=self.link_var, bg=BG, fg=MUTED, font=FONT)
        self.link_label.pack(side="left")
        self.stop_btn = self._button(top, "トルク切断", self._torque_off, fg=BAD)
        self.stop_btn.pack(side="right")

        metrics = tk.Frame(self, bg=BG)
        metrics.pack(fill="x", padx=12, pady=4)
        self.big: dict[str, tk.Label] = {}
        self.big_sub: dict[str, tk.Label] = {}
        for key, title in (
            ("pos", "現在位置"),
            ("spd", "現在速度"),
            ("load", "現在負荷"),
            ("cur", "現在電流"),
            ("volt", "電圧"),
            ("temp", "温度"),
        ):
            card = tk.Frame(metrics, bg=CARD, padx=10, pady=6)
            card.pack(side="left", fill="x", expand=True, padx=3)
            tk.Label(card, text=title, bg=CARD, fg=MUTED, font=FONT_SM).pack(anchor="w")
            value = tk.Label(card, text="—", bg=CARD, fg=TEXT, font=MONO_LG)
            value.pack(anchor="w")
            sub = tk.Label(card, text="", bg=CARD, fg=MUTED, font=FONT_SM)
            sub.pack(anchor="w")
            self.big[key] = value
            self.big_sub[key] = sub

        lamps = tk.Frame(self, bg=BG)
        lamps.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(lamps, text="状態", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(4, 8))
        self.lamps: dict[str, tk.Label] = {}
        for _bit, name in STATUS_BITS:
            lamp = tk.Label(lamps, text=name, bg=CARD, fg=MUTED, font=FONT_SM, padx=8, pady=3)
            lamp.pack(side="left", padx=3)
            self.lamps[name] = lamp
        self.move_lamp = tk.Label(lamps, text="停止", bg=CARD, fg=MUTED, font=FONT_SM, padx=8, pady=3)
        self.move_lamp.pack(side="left", padx=(12, 3))
        self.goal_var = tk.StringVar(value="目標 —")
        tk.Label(lamps, textvariable=self.goal_var, bg=BG, fg=TEXT, font=FONT).pack(side="left", padx=12)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=4)
        body.columnconfigure(0, weight=0, minsize=300)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_controls(body)
        self._build_live(body)
        self._build_graphs(body)
        self._build_bottom()

        hint = (
            "ベースは A・B・GND だけ。12V 端子は空。サーボの VCC だけ 12V、GND は共通。ATOM は USB。"
            "  Esc でもトルク切断。"
        )
        tk.Label(self, text=hint, bg=BG, fg=MUTED, font=FONT_SM, anchor="w").pack(fill="x", padx=14, pady=(0, 8))

    def _build_controls(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg=CARD, padx=12, pady=10)
        box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(box, text="操作", bg=CARD, fg=TEXT, font=(FONT[0], 12, "bold")).pack(anchor="w")
        tk.Label(
            box,
            text="トルク ON は今の角度を保持します。\n位置の指令は、そのあとだけ送れます。",
            bg=CARD,
            fg=MUTED,
            font=FONT_SM,
            justify="left",
        ).pack(anchor="w", pady=(2, 8))

        self.limit_var = tk.StringVar(value="200")
        self.speed_var = tk.StringVar(value="40")
        self.acc_var = tk.StringVar(value="10")
        self._spin_row(box, "トルク制限", self.limit_var, "0〜1000（200 = 20%）")
        self._spin_row(box, "速度", self.speed_var, "1〜32767。0 は最高速になるので不可")
        self._spin_row(box, "加速度", self.acc_var, "0 は最大。10 ≒ 88°/s²")

        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", pady=(8, 4))
        self.apply_btn = self._button(row, "数値だけ書く", self._apply)
        self.apply_btn.pack(side="left")
        self.damp_btn = self._button(row, "ダンパ", self._damp)
        self.damp_btn.pack(side="left", padx=6)

        self.arm_btn = self._button(box, "トルク ON（現在位置を保持）", self._arm, fg=GOOD)
        self.arm_btn.pack(fill="x", pady=(6, 8))

        tk.Label(box, text="目標位置（0〜4095、単圏）", bg=CARD, fg=MUTED, font=FONT_SM).pack(anchor="w")
        self.slider_var = tk.DoubleVar(value=2048)
        self.slider = tk.Scale(
            box,
            from_=0,
            to=4095,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=self.slider_var,
            bg=CARD,
            fg=TEXT,
            troughcolor=CARD_HI,
            highlightthickness=0,
            command=self._on_slider,
        )
        self.slider.pack(fill="x")
        self.slider_caption = tk.StringVar(value="2048   中点から +0.00°")
        tk.Label(box, textvariable=self.slider_caption, bg=CARD, fg=TEXT, font=MONO).pack(anchor="w")

        jog = tk.Frame(box, bg=CARD)
        jog.pack(fill="x", pady=(8, 4))
        self._jog_buttons = []
        for text, deg in (("−15°", -15), ("−5°", -5), ("+5°", 5), ("+15°", 15)):
            button = self._button(jog, text, lambda d=deg: self._jog(d))
            button.pack(side="left", padx=2, expand=True, fill="x")
            self._jog_buttons.append(button)
        self.move_btn = self._button(box, "スライダの位置へ", self._move_slider)
        self.move_btn.pack(fill="x", pady=(6, 0))
        self._set_motion_buttons()

    def _build_live(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg=CARD, padx=10, pady=8)
        box.grid(row=0, column=1, sticky="nsew", padx=6)
        tk.Label(box, text="リアルタイム（アドレス 40〜70）", bg=CARD, fg=TEXT, font=FONT).pack(anchor="w")
        grid = tk.Frame(box, bg=CARD)
        grid.pack(fill="both", expand=True, pady=(6, 0))
        self.live: dict[str, tk.Label] = {}
        names = (
            ("torque", "トルクスイッチ"),
            ("acc", "加速度"),
            ("cmd", "指令位置 42"),
            ("pwm", "PWM 44"),
            ("run", "運行速度 46"),
            ("limit", "トルク制限 48"),
            ("lock", "ロック 55"),
            ("rsv", "予約 50〜54"),
            ("pos", "現在位置 56"),
            ("spd", "現在速度 58"),
            ("load", "現在負荷 60"),
            ("volt", "電圧 62"),
            ("temp", "温度 63"),
            ("async", "非同期書込 64"),
            ("status", "状態 65"),
            ("moving", "移動フラグ 66"),
            ("goal", "目標位置 67"),
            ("curr", "電流 69"),
            ("st", "読出ステータス"),
        )
        for index, (key, title) in enumerate(names):
            col = 0 if index < 10 else 2
            row = index if index < 10 else index - 10
            tk.Label(grid, text=title, bg=CARD, fg=MUTED, font=FONT_SM, anchor="w").grid(
                row=row, column=col, sticky="w", padx=(0, 6), pady=1
            )
            value = tk.Label(grid, text="—", bg=CARD, fg=TEXT, font=MONO, anchor="w")
            value.grid(row=row, column=col + 1, sticky="w", padx=(0, 12), pady=1)
            self.live[key] = value

    def _build_graphs(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg=CARD, padx=8, pady=8)
        box.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        tk.Label(box, text="直近 10 秒", bg=CARD, fg=TEXT, font=FONT).pack(anchor="w")
        self.graphs: list[tuple[tk.Canvas, deque[float], str, str]] = []
        for title, series, color in (
            ("位置 °", self._hist_pos, ACCENT),
            ("速度 rpm", self._hist_spd, GOOD),
            ("電流 mA", self._hist_cur, WARN),
            ("温度 °C", self._hist_tmp, "#ff6b81"),
        ):
            tk.Label(box, text=title, bg=CARD, fg=MUTED, font=FONT_SM).pack(anchor="w", pady=(6, 0))
            canvas = tk.Canvas(box, height=92, bg=BG, highlightthickness=0)
            canvas.pack(fill="x")
            self.graphs.append((canvas, series, color, title))

    def _build_bottom(self) -> None:
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="both", expand=False, padx=12, pady=(4, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        info_card = tk.Frame(bottom, bg=CARD, padx=8, pady=6)
        info_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        head = tk.Frame(info_card, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text="EEPROM と工場領域（接続時に 1 回）", bg=CARD, fg=TEXT, font=FONT).pack(side="left")
        self._button(head, "再読込", self._reload_info).pack(side="right")
        self.info_text = tk.Text(
            info_card,
            height=9,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Yu Gothic UI", 9),
            wrap="word",
        )
        self.info_text.pack(fill="both", expand=True, pady=(4, 0))
        self.info_text.insert("1.0", "未読")
        self.info_text.configure(state="disabled")

        log_card = tk.Frame(bottom, bg=CARD, padx=8, pady=6)
        log_card.grid(row=0, column=1, sticky="nsew")
        tk.Label(log_card, text="通信ログ", bg=CARD, fg=TEXT, font=FONT).pack(anchor="w")
        self.log_text = tk.Text(
            log_card,
            height=9,
            bg=BG,
            fg=MUTED,
            relief="flat",
            font=("Consolas", 9),
            wrap="none",
        )
        self.log_text.pack(fill="both", expand=True, pady=(4, 0))

    def _button(self, parent: tk.Misc, text: str, command, fg: str = TEXT) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=CARD_HI,
            fg=fg,
            activebackground="#2a3848",
            activeforeground=fg,
            relief="flat",
            padx=8,
            pady=4,
            font=FONT,
        )

    def _spin_row(self, parent: tk.Frame, title: str, variable: tk.StringVar, hint: str) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=title, bg=CARD, fg=TEXT, font=FONT, width=10, anchor="w").pack(side="left")
        tk.Entry(
            row,
            textvariable=variable,
            width=8,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
        ).pack(side="left")
        tk.Label(row, text=hint, bg=CARD, fg=MUTED, font=FONT_SM).pack(side="left", padx=6)

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    # ------------------------------------------------------------------
    # 接続
    # ------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        self._ports = list_ports()
        self.port_box["values"] = [label for _device, label in self._ports]
        if self._ports and not self.port_var.get():
            self.port_var.set(self._ports[0][1])

    def _selected_port(self) -> str | None:
        label = self.port_var.get()
        for device, shown in self._ports:
            if shown == label:
                return device
        return None

    def _toggle_connect(self) -> None:
        if self.connected:
            self._disconnect(send_off=True)
        else:
            self._connect()

    def _connect(self) -> None:
        port = self._selected_port()
        if not port:
            messagebox.showwarning("ポート", "ATOM の COM ポートを選んでください。")
            return
        try:
            servo_id = self._servo_id()
        except ValueError as exc:
            messagebox.showwarning("ID", str(exc))
            return
        try:
            self.ser = open_atom_serial(port)
        except serial.SerialException as exc:
            messagebox.showerror("接続", str(exc))
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        self.connected = True
        self.connect_btn.configure(text="切断")
        self.link_var.set(f"{port}  接続中")
        self.link_label.configure(fg=WARN)
        self._log(f"open {port}")
        self._set_motion_buttons()
        # ポートを開いた瞬間にリセットがかかっても、setup が終わるまで待つ。
        self.after(400, lambda sid=servo_id: self._kickoff(sid))

    def _disconnect(self, send_off: bool) -> None:
        if send_off and self.ser is not None:
            # ウィンドウを閉じるとき、出力が残ったままだと軸が保持し続ける。
            self._send("torque 0")
            self._send("stream 0")
            time.sleep(0.2)
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None
        if self.ser is not None:
            try:
                self.ser.dtr = False
                self.ser.close()
            except serial.SerialException:
                pass
            self.ser = None
        self.connected = False
        self.online = False
        self.armed = False
        self._stop_pending = False
        self._pos = None
        self.connect_btn.configure(text="接続")
        self.link_var.set("未接続")
        self.link_label.configure(fg=MUTED)
        self._set_motion_buttons()

    def _send(self, line: str) -> bool:
        ser = self.ser
        if ser is None:
            return False
        try:
            with self._tx_lock:
                ser.write((line.strip() + "\n").encode("ascii"))
        except serial.SerialException as exc:
            self._log(f"送信失敗 {exc}")
            return False
        return True

    def _reader(self) -> None:
        ser = self.ser
        if ser is None:
            return
        buf = b""
        while not self._stop.is_set():
            try:
                chunk = ser.read(256)
            except serial.SerialException as exc:
                self._queue.put(("dead", {"text": str(exc)}))
                return
            if not chunk:
                continue
            buf += chunk
            if len(buf) > 8192 and b"\n" not in buf:
                buf = b""
                continue
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                text = raw.decode("ascii", "replace").strip()
                if not text:
                    continue
                kind, kv = parse_line(text)
                self._queue.put((kind, kv))

    def _kickoff(self, servo_id: int) -> None:
        """接続直後の問い合わせ。切断済みなら何もしない。"""
        if not self.connected:
            return
        self._send(f"id {servo_id}")
        self._send("ping")
        self._send("info")
        self._send(f"stream {STREAM_HZ}")

    def _servo_id(self) -> int:
        try:
            value = int(self.id_var.get().strip(), 10)
        except ValueError as exc:
            raise ValueError("ID は 0〜253 の整数です。") from exc
        if not 0 <= value <= 253:
            raise ValueError("ID は 0〜253 の整数です。")
        return value

    def _motion_args(self) -> tuple[int, int, int] | None:
        try:
            limit = int(self.limit_var.get().strip(), 10)
            speed = int(self.speed_var.get().strip(), 10)
            acc = int(self.acc_var.get().strip(), 10)
        except ValueError:
            messagebox.showwarning("数値", "トルク制限・速度・加速度は整数で入れてください。")
            return None
        if not 0 <= limit <= 1000:
            messagebox.showwarning("トルク制限", "0〜1000 です。1000 が 100%。")
            return None
        if not 1 <= speed <= 32767:
            messagebox.showwarning("速度", "1 以上にしてください。0 は最高速として扱われます。")
            return None
        if not 0 <= acc <= 254:
            messagebox.showwarning("加速度", "0〜254 です。0 は最大加速度です。")
            return None
        return limit, speed, acc

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------

    def _apply_id(self) -> None:
        if not self.connected:
            return
        try:
            servo_id = self._servo_id()
        except ValueError as exc:
            messagebox.showwarning("ID", str(exc))
            return
        # サーボの EEPROM は変えない。ファームが話す宛先だけ変える。
        self.armed = False
        self._send(f"id {servo_id}")
        self._send("ping")
        self._send("info")
        self._set_motion_buttons()

    def _reload_info(self) -> None:
        if self.connected:
            self._send("info")

    def _apply(self) -> None:
        args = self._motion_args()
        if args is None or not self.connected:
            return
        limit, speed, acc = args
        self._send(f"apply {limit} {speed} {acc}")

    def _arm(self) -> None:
        if not self.connected:
            return
        args = self._motion_args()
        if args is None:
            return
        if not messagebox.askokcancel(
            "トルク ON",
            "今の角度を保持します。ホーンの周囲を空けてから進めてください。",
        ):
            return
        limit, speed, acc = args
        self._send(f"arm {limit} {speed} {acc}")

    def _damp(self) -> None:
        if not self.connected:
            return
        args = self._motion_args()
        if args is None:
            return
        if not messagebox.askokcancel("ダンパ", "トルク制限の強さで、外力に対して粘るモードにします。"):
            return
        limit, _speed, _acc = args
        self._send(f"damp {limit}")

    def _torque_off(self) -> None:
        if not self.connected:
            return
        self._stop_pending = True
        self._set_motion_buttons()
        self._send("torque 0")

    def _on_slider(self, _value: str) -> None:
        counts = int(float(self.slider_var.get()))
        # スライダの 0 は単圏の端。中点 2048 からの角度も併記する。
        self.slider_caption.set(f"{counts}   中点から {fmt_deg(counts - 2048)}")

    def _move_slider(self) -> None:
        if self._pos is None or not self._motion_ready():
            return
        target = int(float(self.slider_var.get()))
        delta = target - self._pos
        if abs(delta) > CONFIRM_COUNTS:
            deg = abs(delta) * 360.0 / COUNTS_PER_REV
            if not messagebox.askokcancel("移動", f"現在位置から約 {deg:.0f}° 動かします。進めますか？"):
                return
        self._send(f"move {target}")

    def _jog(self, deg: float) -> None:
        if self._pos is None or not self._motion_ready():
            return
        target = self._pos + counts_from_deg(deg)
        target = max(-32767, min(32767, target))
        self._send(f"move {target}")

    def _motion_ready(self) -> bool:
        return self.connected and self.online and self.armed and not self._stop_pending

    def _set_motion_buttons(self) -> None:
        ready = self._motion_ready()
        state = "normal" if ready else "disabled"
        self.move_btn.configure(state=state)
        for button in self._jog_buttons:
            button.configure(state=state)
        link = "normal" if self.connected else "disabled"
        self.apply_btn.configure(state=link)
        self.arm_btn.configure(state=link)
        self.damp_btn.configure(state=link)
        self.stop_btn.configure(state=link)

    # ------------------------------------------------------------------
    # 受信
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        latest_fb: dict[str, str] | None = None
        events: list[tuple[str, dict[str, str]]] = []
        while True:
            try:
                kind, kv = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "fb":
                latest_fb = kv
            else:
                events.append((kind, kv))
        for kind, kv in events:
            self._dispatch(kind, kv)
        if latest_fb is not None:
            self._on_fb(latest_fb)
        if self.online and (time.monotonic() - self._last_ok) > 0.6:
            self.online = False
            self.link_var.set("応答が途切れています")
            self.link_label.configure(fg=BAD)
            self._set_motion_buttons()
        if self._graph_dirty:
            self._draw_graphs()
            self._graph_dirty = False
        self.after(50, self._tick)

    def _dispatch(self, kind: str, kv: dict[str, str]) -> None:
        if kind == "ok":
            self._on_ok(kv)
        elif kind == "err":
            self._on_err(kv)
        elif kind == "info":
            self._on_info(kv)
        elif kind == "hello":
            self._on_hello(kv)
        elif kind == "dead":
            self._log(f"ポートが落ちました: {kv.get('text', '')}")
            self._disconnect(send_off=False)
        elif kind == "log":
            self._log(kv.get("text", ""))

    def _on_hello(self, kv: dict[str, str]) -> None:
        self._log(
            f"hello rx={kv.get('rx')} tx={kv.get('tx')} baud={kv.get('baud')} self={kv.get('self', '?')}"
        )
        if kv.get("self") == "0":
            self._log("ファームのチェックサム自己検査に失敗しています。焼き直してください。")

    def _on_ok(self, kv: dict[str, str]) -> None:
        cmd = kv.get("cmd", "")
        if cmd == "ping":
            self.link_var.set(f"PING 応答  ID {kv.get('id', '?')}  st={kv.get('st', '?')}")
            self.link_label.configure(fg=GOOD)
            self._log(f"ping id={kv.get('id')} st={kv.get('st')}")
        elif cmd == "arm":
            self.armed = True
            self._stop_pending = False
            pos = _int_token(kv, "pos")
            self._log(f"保持を開始 pos={pos} st={kv.get('st')}")
            if pos is not None and not self._slider_ready:
                self._sync_slider(pos)
            self._set_motion_buttons()
        elif cmd == "damp":
            self.armed = True
            self._stop_pending = False
            self._log(f"ダンパ st={kv.get('st')}")
            self._set_motion_buttons()
        elif cmd == "torque" and kv.get("value") == "0":
            self.armed = False
            self._stop_pending = False
            self._log("トルク切断")
            self._set_motion_buttons()
        elif cmd in ("apply", "id", "stream", "move"):
            self._log(" ".join(f"{key}={value}" for key, value in kv.items()))
            if cmd == "id":
                self.armed = False
                self._set_motion_buttons()
        else:
            self._log(" ".join(f"{key}={value}" for key, value in kv.items()))

    def _on_err(self, kv: dict[str, str]) -> None:
        cmd = kv.get("cmd", "?")
        msg = kv.get("msg", "")
        tx = kv.get("tx", "")
        self._log(f"ERR {cmd} {msg} {tx}".strip())
        if cmd == "torque":
            self._stop_pending = False
            self._set_motion_buttons()
        if cmd == "ping":
            self.link_var.set("PING 応答なし。A/B、GND、12V、ID を確認")
            self.link_label.configure(fg=BAD)
        reasons = {
            "timeout": "サーボが応答しません",
            "torque_off": "トルクが入っていないので、位置は送っていません",
            "write_goal": "目標の書き込みに失敗したので、切断を試みました",
            "use_arm_or_off": "トルク ON は arm だけが行います",
            "bad_arg": "範囲外の数値です",
        }
        if msg in reasons and cmd in ("arm", "move", "torque", "ping"):
            self.link_var.set(reasons[msg])
            self.link_label.configure(fg=BAD)

    def _on_fb(self, kv: dict[str, str]) -> None:
        if kv.get("ok") != "1":
            self.online = False
            self.link_var.set("フィードバック応答なし")
            self.link_label.configure(fg=BAD)
            self._set_motion_buttons()
            return
        self.online = True
        now = time.monotonic()
        self._last_ok = now
        self._fb_times.append(now)
        hz = self._estimate_hz()
        self.link_var.set(f"受信中  {hz:.0f} Hz  ID {kv.get('id', '?')}")
        self.link_label.configure(fg=GOOD)

        pos_raw = _int_token(kv, "pos") or 0
        spd_raw = _int_token(kv, "spd") or 0
        load_raw = _int_token(kv, "load") or 0
        goal_raw = _int_token(kv, "goal") or 0
        cmd_raw = _int_token(kv, "cmd_pos") or 0
        pwm_raw = _int_token(kv, "pwm") or 0
        run_raw = _int_token(kv, "run_spd") or 0
        curr_raw = _int_token(kv, "curr") or 0
        volt_raw = _int_token(kv, "volt") or 0
        temp = _int_token(kv, "temp") or 0
        torque = _int_token(kv, "torque") or 0
        status = _int_token(kv, "status") or 0
        moving = _int_token(kv, "moving") or 0

        pos = decode_bit15(pos_raw)
        spd = decode_bit15(spd_raw)
        load = decode_bit10(load_raw)
        goal = decode_bit15(goal_raw)
        cmd = decode_bit15(cmd_raw)
        pwm = decode_bit10(pwm_raw)
        run = decode_bit15(run_raw)
        unit = 0.0146 if (self._phase & PHASE_SPEED_FINE) else 0.732
        self._pos = pos
        if not self._slider_ready:
            self._sync_slider(pos)

        # 保護でサーボが自分から出力を切ることがある。GUI 側の許可だけ残さない。
        if self.armed and torque == 0 and not self._stop_pending:
            self.armed = False
            self._log("サーボがトルクを切りました（保護か、外部からの切断）")
            self._set_motion_buttons()

        # 大きな数字は中点 2048 からの角度。0 カウントは -180°、2048 は 0°。
        self.big["pos"].configure(text=fmt_deg(pos - 2048), fg=TEXT)
        self.big_sub["pos"].configure(text=f"中点基準  {pos} count  raw {pos_raw}")
        self.big["spd"].configure(text=f"{spd * unit:+.2f}", fg=TEXT)
        self.big_sub["spd"].configure(text=f"rpm  raw {spd_raw}")
        self.big["load"].configure(text=f"{load / 10.0:+.1f}%", fg=TEXT)
        self.big_sub["load"].configure(text=f"raw {load_raw}")
        self.big["cur"].configure(text=f"{curr_raw * 6.5:.0f}", fg=TEXT)
        self.big_sub["cur"].configure(text="mA")
        self.big["volt"].configure(text=f"{volt_raw / 10.0:.1f}", fg=TEXT)
        self.big_sub["volt"].configure(text="V")
        self.big["temp"].configure(text=f"{temp}", fg=WARN if temp >= 60 else TEXT)
        self.big_sub["temp"].configure(text="°C")
        self.goal_var.set(f"目標 {fmt_deg(goal)}   残り {fmt_deg(goal - pos)}")

        acc = _int_token(kv, "acc") or 0
        limit = _int_token(kv, "limit") or 0
        self.live["torque"].configure(text=f"{TORQUE_NAME.get(torque, str(torque))}  ({torque})")
        self.live["acc"].configure(text="最大" if acc == 0 else f"{acc}  ({acc * 8.79:.0f}°/s²)")
        self.live["cmd"].configure(text=f"{fmt_deg(cmd)}  raw {cmd_raw}")
        self.live["pwm"].configure(text=f"{pwm / 10.0:+.1f}%  raw {pwm_raw}")
        self.live["run"].configure(text=f"{run * unit:+.2f} rpm  raw {run_raw}")
        self.live["limit"].configure(text=f"{limit / 10.0:.1f}%  raw {limit}")
        self.live["lock"].configure(text=str(_int_token(kv, "lock")))
        self.live["rsv"].configure(
            text=" ".join(str(_int_token(kv, key) or 0) for key in ("r0", "r1", "r2", "r3", "r4"))
        )
        self.live["pos"].configure(text=f"{pos}  raw {pos_raw}")
        self.live["spd"].configure(text=f"{spd}  raw {spd_raw}")
        self.live["load"].configure(text=f"{load}  raw {load_raw}")
        self.live["volt"].configure(text=f"{volt_raw / 10.0:.1f} V  raw {volt_raw}")
        self.live["temp"].configure(text=f"{temp} °C")
        self.live["async"].configure(text=str(_int_token(kv, "async")))
        self.live["status"].configure(text=self._status_text(status))
        self.live["moving"].configure(text="移動中" if moving else "停止")
        self.live["goal"].configure(text=f"{goal}  raw {goal_raw}")
        self.live["curr"].configure(text=f"{curr_raw * 6.5:.1f} mA  raw {curr_raw}")
        self.live["st"].configure(text=str(_int_token(kv, "st")))

        for bit, name in STATUS_BITS:
            on = bool(status & bit)
            self.lamps[name].configure(bg=BAD if on else CARD, fg="white" if on else GOOD)
        self.move_lamp.configure(
            text="移動中" if moving else "停止",
            fg=ACCENT if moving else MUTED,
        )

        self._hist_pos.append((pos - 2048) * 360.0 / COUNTS_PER_REV)
        self._hist_spd.append(spd * unit)
        self._hist_cur.append(curr_raw * 6.5)
        self._hist_tmp.append(float(temp))
        self._graph_dirty = True
        self._set_motion_buttons()

    def _on_info(self, kv: dict[str, str]) -> None:
        phase = _int_token(kv, "phase")
        if phase is not None:
            self._phase = phase
        self._set_text(self.info_text, format_info(kv))
        self._log(
            f"info id={kv.get('id')} baud={kv.get('baud_bps')} mode={kv.get('mode')} fact={kv.get('fact')}"
        )

    def _sync_slider(self, pos: int) -> None:
        """最初の 1 回だけ現在位置をスライダに写す。毎フレーム写すと操作が打ち消される。"""
        if self._slider_ready:
            return
        if 0 <= pos <= 4095:
            self.slider_var.set(pos)
            self._on_slider(str(pos))
        self._slider_ready = True

    def _estimate_hz(self) -> float:
        if len(self._fb_times) < 2:
            return 0.0
        span = self._fb_times[-1] - self._fb_times[0]
        if span <= 0:
            return 0.0
        return (len(self._fb_times) - 1) / span

    def _status_text(self, status: int) -> str:
        if status == 0:
            return "0 正常"
        names = [name for bit, name in STATUS_BITS if status & bit]
        return f"{status}  {' '.join(names) if names else '異常'}"

    def _log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"{stamp}  {text}\n")
        self.log_text.see("end")
        # 試験中に流しっぱなしでも、古い行でメモリを食わないようにする。
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 200:
            self.log_text.delete("1.0", "80.0")

    def _draw_graphs(self) -> None:
        for canvas, series, color, _title in self.graphs:
            canvas.delete("all")
            width = max(canvas.winfo_width(), 10)
            height = max(canvas.winfo_height(), 10)
            canvas.create_line(0, height / 2, width, height / 2, fill=GRID)
            if len(series) < 2:
                continue
            low = min(series)
            high = max(series)
            if high - low < 1e-6:
                high = low + 1.0
            pad = (high - low) * 0.1
            low -= pad
            high += pad

            def x_of(index: int, n: int = len(series), w: int = width) -> float:
                return index * (w - 1) / (n - 1)

            def y_of(value: float, lo: float = low, hi: float = high, h: int = height) -> float:
                return h - 1 - (value - lo) / (hi - lo) * (h - 1)

            points: list[float] = []
            for index, value in enumerate(series):
                points.extend((x_of(index), y_of(value)))
            canvas.create_line(*points, fill=color, width=2)

    def _on_close(self) -> None:
        self._closing = True
        self._disconnect(send_off=True)
        self.destroy()


def _bits(value: int, table: tuple[tuple[int, str], ...]) -> str:
    names = [name for bit, name in table if value & bit]
    return "、".join(names) if names else "なし"


def decode_offset(raw: int) -> int:
    """アドレス 31。0〜8191 を符号付きオフセットに戻す。範囲外はそのまま。"""
    if 0 <= raw <= 2047:
        return raw
    if 2048 <= raw <= 4095:
        return -(raw - 2048)
    if 4096 <= raw <= 6143:
        return raw - 2048
    if 6144 <= raw <= 8191:
        return -(raw - 4096)
    return raw


def format_info(kv: dict[str, str]) -> str:
    """接続時に 1 度読む領域。動いている量は上のリアルタイム側。"""

    def num(key: str) -> int:
        return _int_token(kv, key) or 0

    lines: list[str] = []
    if num("endian") != 0:
        lines.append("エンディアンが 0 ではありません。この画面の 16bit 解釈は合いません。")
    if num("level") == 0:
        lines.append("応答レベルが 0 です。PING と読出以外は返事がないので、トルク操作は失敗します。")
    lines.append(
        f"ファーム {num('fw_maj')}.{num('fw_min')}    サーボ {num('srv_maj')}.{num('srv_min')}"
        f"    EEPROM上のID {num('id')}    ボーレート {num('baud_bps')} bps（段 {num('baud')}）"
    )
    lines.append(
        f"角度制限 {num('amin')}〜{num('amax')}（{fmt_deg(num('amin'))}〜{fmt_deg(num('amax'))}）"
        f"    分解能係数 {num('res')}    位置オフセット {decode_offset(num('ofs'))}（raw {num('ofs')}）"
    )
    lines.append(
        f"モード {MODE_NAME.get(num('mode'), str(num('mode')))}"
        f"    応答遅延 {num('delay')}    応答レベル {num('level')}"
        f"    最大トルク {num('max_trq') / 10:.1f}%"
    )
    vmax = num("vmax")
    vmin = num("vmin")
    lines.append(
        f"温度上限 {num('tmax')}°C    電圧 {vmin / 10:.1f}〜{vmax / 10:.1f} V"
        f"（raw {vmin}〜{vmax}）    保護電流 {num('prot_i') * 6.5:.0f} mA"
    )
    lines.append(
        f"PID P{num('kp')} D{num('kd')} I{num('ki')}"
        f"    最低起動トルク {num('start_trq')}    積分制限 {num('ilimit')}"
        f"    不感帯 +{num('db_cw')} / −{num('db_ccw')}"
    )
    lines.append(
        f"過載 {num('oload')}% が {num('ptime') * 10} ms 続いたら保持 {num('hold')}%"
        f"    過流保護時間 {num('oc_time') * 10} ms"
        f"    速度P {num('spd_p')} 速度I {num('spd_i')}"
    )
    phase = num("phase")
    lines.append("位相 " + _bits(phase, (
        (1, "駆動反転"),
        (2, "ブラシ"),
        (4, "速度単位 0.0146rpm"),
        (8, "速度0は最高速"),
        (16, "全角度フィードバック"),
        (32, "高圧サンプリング"),
        (64, "PWM 16kHz"),
        (128, "位置フィードバック反転"),
    )) + f"（raw {phase}）")
    lines.append("アンロード " + _bits(num("unload"), STATUS_BITS) + f"（raw {num('unload')}）")
    lines.append("LED警報 " + _bits(num("led"), STATUS_BITS) + f"（raw {num('led')}）")
    if num("fact"):
        lines.append(
            f"工場 速度閾値 {num('thr')}  DTs {num('dts')}  速度係数 {num('spd_k')}"
            f"  HTs {num('hts')}  最高速 {num('spd_max')}  加速度制限 {num('acc_max')}"
            f"  加速度倍数 {num('acc_mul')}"
        )
    else:
        lines.append("工場領域（80〜86）は読めませんでした。")
    return "\n".join(lines)


def main() -> None:
    _self_check()
    app = ServoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
