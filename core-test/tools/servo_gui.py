#!/usr/bin/env python3
"""
SM105BL の机上試験。サブ PC は CoreS3 の USB だけを開く。

CoreS3（core-test）が Grove へ行を渡し、ATOM S3R（grove-rs485）が RS485 を話す。
ATOM の USB は挿さない。電源は Grove の 5V。サーボの 12V は別。

接続してもトルクは入らない。トルク ON は、今の位置を目標にして保持させる。
目標が 0 のまま出力すると、中点付近から 0 カウントへ回るため。

起動:
    pip install -r tools/requirements.txt
    python tools/servo_gui.py

CoreS3 は core-test で pio run -t upload。
ATOM は atom-test で pio run -e grove-rs485 -t upload。書くときは Grove を外す。
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import serial
import serial.tools.list_ports

BAUD = 115200
STREAM_HZ = 20
# 1 周 4096。1 カウントは 360/4096 度（約 0.0879°）。中点は 2048。
COUNTS_PER_REV = 4096
# これより大きい絶対移動は、押す前に確認する。150 kg·cm なので半周は遠すぎる。
CONFIRM_COUNTS = 512  # 45°
# CoreS3 の hello がこの時間来なければ、別ファームの COM を開いている。
CORE_HELLO_WAIT_S = 1.5
# Grove の 5V のあと ATOM が起動するまで。これを超えたら配線を疑う。
ATOM_HELLO_WAIT_S = 2.0

BG = "#0e1318"
CARD = "#17202a"
CARD_HI = "#1f2a36"
TEXT = "#e8eef4"
MUTED = "#8b9bb0"
GOOD = "#10ac84"
BAD = "#ee5253"
WARN = "#feca57"
ACCENT = "#54a0ff"
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


def is_m5_hwid(hwid: str | None) -> bool:
    return "303A" in (hwid or "")


def list_ports() -> list[tuple[str, str]]:
    """(COM, 表示)。Espressif VID 303A を先頭にする。ATOM の USB は挿さない。"""
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=lambda p: (0 if is_m5_hwid(p.hwid) else 1, p.device))
    labeled = []
    for port in ports:
        mark = "M5 " if is_m5_hwid(port.hwid) else ""
        desc = port.description or ""
        labeled.append((port.device, f"{mark}{port.device}  {desc}".strip()))
    return labeled


def open_core_serial(port: str) -> serial.Serial:
    """DTR を立てると USB を開くたびに CoreS3 がリセットされ、Grove の 5V が一度落ちる。"""
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
        self.title("SM105BL  /  CoreS3 → ATOM S3R")
        self.configure(bg=BG)
        self.minsize(980, 720)
        self.geometry("1080x780")

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
        self._slider_ready = False
        self._port_name = ""
        self._servo_id_pending = 1
        # ATOM の hello を見てから問い合わせる。起動前に送った行は消える。
        self._queried = False

        # None はまだ hello を見ていない。False は見たうえでダメだった。
        self.grove_on: bool | None = None
        self.atom_seen = False
        self.atom_self: int | None = None
        self._core_at: float | None = None
        self._atom_at: float | None = None
        self._connected_at = 0.0
        # リンクが自分から切ったとき。次の正常な fb までバナーに残す。
        self._link_fault = ""

        self._build()
        self._refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _event: self._torque_off())
        self.after(50, self._tick)

    def _build(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="CoreS3", bg=BG, fg=MUTED, font=FONT).pack(side="left")
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
        self.stop_btn = self._button(top, "トルク切断", self._torque_off, fg=BAD)
        self.stop_btn.pack(side="right")

        chips = tk.Frame(self, bg=BG)
        chips.pack(fill="x", padx=12, pady=(0, 4))
        self.chips: dict[str, tk.Label] = {}
        for key, title in (("usb", "USB"), ("grove", "Grove 5V"), ("atom", "ATOM"), ("servo", "サーボ")):
            lamp = tk.Label(chips, text=f"{title}  —", bg=CARD, fg=MUTED, font=FONT_SM, padx=10, pady=4)
            lamp.pack(side="left", padx=(0, 6))
            self.chips[key] = lamp
        self.link_var = tk.StringVar(value="未接続")
        self.link_label = tk.Label(chips, textvariable=self.link_var, bg=BG, fg=MUTED, font=FONT)
        self.link_label.pack(side="left", padx=8)

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
        body.columnconfigure(0, weight=0, minsize=340)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_controls(body)
        self._build_side(body)

        hint = (
            "CoreS3 の USB だけを開く。ATOM の USB は抜く。ストレートの Grove を PORT.B へ。"
            " 赤が 5V、黄が送信、白が受信。サーボの VCC だけ 12V。Esc でもトルク切断。"
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

    def _build_side(self, parent: tk.Frame) -> None:
        side = tk.Frame(parent, bg=BG)
        side.grid(row=0, column=1, sticky="nsew")
        side.rowconfigure(0, weight=1)
        side.rowconfigure(1, weight=1)
        side.columnconfigure(0, weight=1)

        info_card = tk.Frame(side, bg=CARD, padx=8, pady=6)
        info_card.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        head = tk.Frame(info_card, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text="EEPROM と工場領域（接続時に 1 回）", bg=CARD, fg=TEXT, font=FONT).pack(side="left")
        self._button(head, "再読込", self._reload_info).pack(side="right")
        self.info_text = tk.Text(
            info_card,
            height=8,
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

        log_card = tk.Frame(side, bg=CARD, padx=8, pady=6)
        log_card.grid(row=1, column=0, sticky="nsew")
        tk.Label(log_card, text="通信ログ", bg=CARD, fg=TEXT, font=FONT).pack(anchor="w")
        self.log_text = tk.Text(
            log_card,
            height=8,
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

    def _chip(self, key: str, text: str, fg: str) -> None:
        self.chips[key].configure(text=text, fg=fg)

    def _paint_chips(self) -> None:
        if not self.connected:
            for key, title in (("usb", "USB"), ("grove", "Grove 5V"), ("atom", "ATOM"), ("servo", "サーボ")):
                self._chip(key, f"{title}  —", MUTED)
            return
        self._chip("usb", "USB  接続", GOOD)
        if self.grove_on is True:
            self._chip("grove", "Grove 5V  オン", GOOD)
        elif self.grove_on is False:
            self._chip("grove", "Grove 5V  オフ", BAD)
        else:
            self._chip("grove", "Grove 5V  不明", WARN)
        if self.atom_self == 0:
            self._chip("atom", "ATOM  自己検査失敗", BAD)
        elif self.atom_seen:
            self._chip("atom", "ATOM  応答", GOOD)
        elif self._core_at is not None and (time.monotonic() - self._core_at) > ATOM_HELLO_WAIT_S:
            self._chip("atom", "ATOM  無応答", BAD)
        else:
            self._chip("atom", "ATOM  待ち", WARN)
        if self.online:
            self._chip("servo", "サーボ  受信中", GOOD)
        elif self._link_fault:
            self._chip("servo", "サーボ  切断", BAD)
        else:
            self._chip("servo", "サーボ  待ち", WARN)

    def _refresh_banner(self) -> None:
        """どこで止まっているかを、サーボの故障と混ぜない。"""
        if not self.connected:
            self.link_var.set("未接続")
            self.link_label.configure(fg=MUTED)
            return
        if self.grove_on is False:
            self.link_var.set("Grove 5V がオフです。ATOM は起動しません")
            self.link_label.configure(fg=BAD)
            return
        now = time.monotonic()
        if self._core_at is None:
            if now - self._connected_at > CORE_HELLO_WAIT_S:
                self.link_var.set("CoreS3 の hello がありません。core-test を焼いてください")
                self.link_label.configure(fg=BAD)
            else:
                self.link_var.set(f"{self._port_name}  hello 待ち")
                self.link_label.configure(fg=WARN)
            return
        if self.atom_self == 0:
            self.link_var.set("ATOM のパケット自己検査に失敗しています")
            self.link_label.configure(fg=BAD)
            return
        if not self.atom_seen:
            if now - self._core_at > ATOM_HELLO_WAIT_S:
                self.link_var.set("ATOM が無応答です。Grove の黄・白・赤・黒を確認")
                self.link_label.configure(fg=BAD)
            else:
                self.link_var.set("ATOM の起動待ち")
                self.link_label.configure(fg=WARN)
            return
        if self._link_fault:
            self.link_var.set(self._link_fault)
            self.link_label.configure(fg=BAD)
            return
        if self.online:
            return
        self.link_var.set("ATOM は応答しています。サーボの周期データ待ち")
        self.link_label.configure(fg=WARN)

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
            messagebox.showwarning("ポート", "CoreS3 の COM ポートを選んでください。")
            return
        try:
            servo_id = self._servo_id()
        except ValueError as exc:
            messagebox.showwarning("ID", str(exc))
            return
        try:
            self.ser = open_core_serial(port)
        except serial.SerialException as exc:
            messagebox.showerror("接続", str(exc))
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        self.connected = True
        self._port_name = port
        self._connected_at = time.monotonic()
        self.grove_on = None
        self.atom_seen = False
        self.atom_self = None
        self._core_at = None
        self._atom_at = None
        self._link_fault = ""
        self.online = False
        self._servo_id_pending = servo_id
        self._queried = False
        self.connect_btn.configure(text="切断")
        self._log(f"open {port}")
        self._set_motion_buttons()
        self._paint_chips()
        self._refresh_banner()
        # 開いた瞬間にリセットがかかっても、5V が出てから hello を送る。
        self.after(700, self._kickoff)

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
        self.grove_on = None
        self.atom_seen = False
        self.atom_self = None
        self._core_at = None
        self._atom_at = None
        self._link_fault = ""
        self._queried = False
        self.connect_btn.configure(text="接続")
        self._set_motion_buttons()
        self._paint_chips()
        self._refresh_banner()

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

    def _kickoff(self) -> None:
        """hello だけ先に出す。サーボへの問い合わせは ATOM の hello のあと。"""
        if not self.connected:
            return
        self._send("hello")
        if self.atom_seen:
            self._query_servo()

    def _query_servo(self) -> None:
        # 起動前に送った ping は ATOM がいないので消える。hello を見てから出す。
        if self._queried or not self.connected:
            return
        self._queried = True
        servo_id = self._servo_id_pending
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

    def _link_ready_for_torque(self) -> bool:
        """5V と ATOM が見えていない状態では、軸を動かさない。"""
        if self.grove_on is False:
            messagebox.showwarning("Grove 5V", "CoreS3 が 5V を出せていません。ATOM は起動していません。")
            return False
        if not self.atom_seen or self.atom_self == 0:
            messagebox.showwarning("ATOM", "ATOM の hello がまだ正常に来ていません。Grove を確認してください。")
            return False
        return True

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
        if not self.connected or not self._link_ready_for_torque():
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
        if not self.connected or not self._link_ready_for_torque():
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
        return self.connected and self.online and self.armed and not self._stop_pending and self.grove_on is not False

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
            self._link_fault = "サーボのフィードバックが途切れています"
            self._set_motion_buttons()
        self._paint_chips()
        self._refresh_banner()
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
        name = kv.get("name", "")
        if name == "core-test":
            self._core_at = time.monotonic()
            grove = kv.get("grove")
            if grove == "1":
                self.grove_on = True
            elif grove == "0":
                self.grove_on = False
            self._log(
                f"CoreS3 grove={kv.get('grove', '?')} tx={kv.get('tx')} rx={kv.get('rx')} baud={kv.get('baud')}"
            )
            return
        if name == "grove-rs485":
            self._atom_at = time.monotonic()
            self.atom_seen = True
            self.atom_self = _int_token(kv, "self")
            self._log(
                f"ATOM id={kv.get('id')} self={kv.get('self', '?')} baud={kv.get('baud')}"
            )
            if self.atom_self == 0:
                self._log("ATOM のチェックサム自己検査に失敗しています。焼き直してください。")
            else:
                self._query_servo()
            return
        # 別ファームの hello。CoreS3 経由なら名前があるはずなので、ログだけ残す。
        self._log("hello " + " ".join(f"{key}={value}" for key, value in kv.items()))

    def _on_ok(self, kv: dict[str, str]) -> None:
        cmd = kv.get("cmd", "")
        if cmd == "ping":
            self._link_fault = ""
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
            if kv.get("reason") == "timeout":
                self._link_fault = "Grove が途切れたので ATOM がトルクを切りました"
                self._log(self._link_fault)
            else:
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
        reasons = {
            "timeout": "サーボが応答しません。A/B、GND、12V、ID を確認",
            "torque_off": "トルクが入っていないので、位置は送っていません",
            "write_goal": "目標の書き込みに失敗したので、切断を試みました",
            "use_arm_or_off": "トルク ON は arm だけが行います",
            "bad_arg": "範囲外の数値です",
            "long": "行が長すぎて ATOM が捨てました",
        }
        if msg in reasons and self.grove_on is not False:
            self._link_fault = reasons[msg]
            self._set_motion_buttons()

    def _on_fb(self, kv: dict[str, str]) -> None:
        if kv.get("ok") != "1":
            self.online = False
            self._link_fault = "サーボがフィードバックに応答しません"
            self._set_motion_buttons()
            return
        self.online = True
        self._link_fault = ""
        self._last_ok = time.monotonic()
        self.link_var.set(f"受信中  ID {kv.get('id', '?')}")
        self.link_label.configure(fg=GOOD)

        pos_raw = _int_token(kv, "pos") or 0
        spd_raw = _int_token(kv, "spd") or 0
        load_raw = _int_token(kv, "load") or 0
        goal_raw = _int_token(kv, "goal") or 0
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
        unit = 0.0146 if (self._phase & PHASE_SPEED_FINE) else 0.732
        self._pos = pos
        if not self._slider_ready:
            self._sync_slider(pos)

        # 保護でサーボが自分から出力を切ることがある。GUI 側の許可だけ残さない。
        if self.armed and torque == 0 and not self._stop_pending:
            self.armed = False
            self._log("サーボがトルクを切りました（保護か、外部からの切断）")
            self._set_motion_buttons()

        self.big["pos"].configure(text=fmt_deg(pos - 2048), fg=TEXT)
        self.big_sub["pos"].configure(text=f"中点基準  {pos} count  raw {pos_raw}")
        self.big["spd"].configure(text=f"{spd * unit:+.2f}", fg=TEXT)
        self.big_sub["spd"].configure(text="rpm")
        self.big["load"].configure(text=f"{load / 10.0:+.1f}%", fg=TEXT)
        self.big_sub["load"].configure(text=f"raw {load_raw}")
        self.big["cur"].configure(text=f"{curr_raw * 6.5:.0f}", fg=TEXT)
        self.big_sub["cur"].configure(text="mA")
        self.big["volt"].configure(text=f"{volt_raw / 10.0:.1f}", fg=TEXT)
        self.big_sub["volt"].configure(text="V")
        self.big["temp"].configure(text=f"{temp}", fg=WARN if temp >= 60 else TEXT)
        self.big_sub["temp"].configure(text="°C")
        self.goal_var.set(f"目標 {fmt_deg(goal)}   残り {fmt_deg(goal - pos)}")

        for bit, name in STATUS_BITS:
            on = bool(status & bit)
            self.lamps[name].configure(bg=BAD if on else CARD, fg="white" if on else GOOD)
        self.move_lamp.configure(
            text="移動中" if moving else "停止",
            fg=ACCENT if moving else MUTED,
        )
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

    def _log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"{stamp}  {text}\n")
        self.log_text.see("end")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 200:
            self.log_text.delete("1.0", "80.0")

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
    """接続時に 1 度読む領域。動いている量は上の数字。"""

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
