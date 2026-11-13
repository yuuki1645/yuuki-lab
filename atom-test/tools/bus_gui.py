#!/usr/bin/env python3
"""
SM105BL と ATOM S3R（LTC1480）の RS485 を、USB の行テキストから見る。

ファーム（atom-test の環境 rs485）がバスを話し、この GUI はバイト列を色分けする。
接続しただけでは軸は動かない。トルク ON は今の位置を保持し、バーは離したときだけ動く。

起動:
    pip install -r tools/requirements.txt
    python tools/bus_gui.py

書き込みは atom-test で pio run -e rs485 -t upload。
引数なしの upload は hello のままなので、この画面には出てこない。
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import messagebox, ttk

import serial
import serial.tools.list_ports

BAUD = 115200
MAX_ROWS = 100
# 1 周 4096。中点 2048 を 0° として表示する。atom-rs485 の試験画面と同じ。
COUNTS_PER_REV = 4096
# これより大きい移動は、送る前に確認する。
CONFIRM_COUNTS = 512
TORQUE_NAME = {0: "切断", 1: "出力中", 2: "ダンパ"}

# サーボのアドレス 6。ファームの kServoBauds と同じ並び。UART が今話している速度とは別。
SERVO_BAUDS = (1000000, 500000, 250000, 128000, 115200, 76800, 57600, 38400)
INST_NAME = {0x01: "PING", 0x02: "READ", 0x03: "WRITE"}

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
MONO = ("Consolas", 11)
MONO_LG = ("Consolas", 26, "bold")


@dataclass
class Packet:
    servo_id: int
    length: int
    head: int
    params: bytes
    cs_ok: bool


@dataclass
class TraceRow:
    kind: str
    tone: str
    when: str
    note: str = ""
    tx: bytes = b""
    rx: bytes = b""
    echo: bool = False
    us: int = 0
    timeout: bool = False
    baud: int = 0
    raw_rx: str = ""
    extras: dict[str, str] = field(default_factory=dict)


def _self_check() -> None:
    """ファームの自己検査と同じバイト列で、チェックサムがずれていないことを確認する。"""
    ping = build_packet(1, 0x01, b"")
    read = build_packet(1, 0x02, bytes((0x28, 0x1F)))
    reply = build_packet(1, 0x00, b"")
    write_off = build_packet(1, 0x03, bytes((0x28, 0x00)))
    assert ping == bytes.fromhex("ffff010201fb")
    assert read == bytes.fromhex("ffff010402281fb1")
    assert reply == bytes.fromhex("ffff010200fc")
    assert write_off == bytes.fromhex("ffff0104032800cf")
    assert parse_packet(ping) is not None and parse_packet(ping).cs_ok
    assert "ボーレート" in timeout_reason(True, 0)
    assert "3.3V" in timeout_reason(False, 0)
    assert decode_bit15(0x8000 | 100) == -100
    assert decode_bit10(0x0400 | 100) == -100
    assert counts_from_deg(90) == 1024
    assert is_live_read(read)
    assert not is_live_read(ping)
    kind, kv = parse_line("@bus ms=1 us=840 echo=1 baud=115200 tx=ffff010201fb rx=ffff010200fc st=0")
    assert kind == "bus" and kv["echo"] == "1" and kv["rx"] == "ffff010200fc"


def build_packet(servo_id: int, head: int, params: bytes) -> bytes:
    """指令もステータスも同じ枠。Length は head、パラメータ、チェックサムのバイト数。"""
    length = len(params) + 2
    body = bytes((servo_id, length, head)) + params
    return b"\xff\xff" + body + bytes(((~sum(body)) & 0xFF,))


def parse_packet(pkt: bytes) -> Packet | None:
    if len(pkt) < 6 or pkt[0] != 0xFF or pkt[1] != 0xFF:
        return None
    length = pkt[3]
    if length < 2 or len(pkt) != length + 4:
        return None
    cs_ok = ((~sum(pkt[2:-1])) & 0xFF) == pkt[-1]
    return Packet(pkt[2], length, pkt[4], pkt[5:-1], cs_ok)


def decode_bit15(raw: int) -> int:
    """ビット15が方向、下位15ビットが大きさ。位置と速度。"""
    if raw & 0x8000:
        return -(raw & 0x7FFF)
    return raw & 0x7FFF


def decode_bit10(raw: int) -> int:
    """ビット10が方向、下位10ビットが大きさ。負荷。"""
    sign = -1 if (raw & 0x0400) else 1
    return sign * (raw & 0x03FF)


def counts_from_deg(deg: float) -> int:
    return int(round(deg * COUNTS_PER_REV / 360.0))


def fmt_deg(counts: int) -> str:
    return f"{counts * 360.0 / COUNTS_PER_REV:+.2f}°"


def is_live_read(tx: bytes) -> bool:
    """位置の定期読み（アドレス 40 から 31 バイト）。ログでは 1 行だけ更新する。"""
    pkt = parse_packet(tx)
    return pkt is not None and pkt.head == 0x02 and pkt.params == bytes((40, 31))


def parse_hex(text: str) -> bytes | None:
    text = text.strip()
    if text == "":
        return b""
    if len(text) % 2 != 0:
        return None
    try:
        return bytes.fromhex(text)
    except ValueError:
        return None


def parse_line(text: str) -> tuple[str, dict[str, str]]:
    """`@bus k=v ...` を (種別, 辞書) にする。@ が無ければ log。"""
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


def fmt_us(us: int) -> str:
    ms = us / 1000.0
    if ms >= 10:
        return f"{ms:.1f} ms"
    return f"{ms:.2f} ms"


def timeout_reason(echo: bool, n: int) -> str:
    """エコーはサーボがいなくても戻る。無音と「サーボだけ無い」を混ぜない。"""
    if n == 0 and not echo:
        return "受信なし。DI、RO、DE、3.3V、GND を確認"
    if n == 0 and echo:
        return "エコーのみ。サーボの返事がない。12V、共通 GND、A/B、ID、ボーレートを確認"
    if echo:
        return "バイトは届いたが返事になっていない。ボーレートが違うことがある"
    return "自分の送信は見えていない。届いた列を確認"


def master_text(pkt: Packet, baud: int) -> str:
    name = INST_NAME.get(pkt.head, f"INST {pkt.head:02X}")
    if pkt.head == 0x01:
        text = f"PING  ID {pkt.servo_id}"
    elif pkt.head == 0x02 and len(pkt.params) >= 2:
        text = f"READ  addr {pkt.params[0]}  len {pkt.params[1]}"
    elif pkt.head == 0x03 and len(pkt.params) >= 1:
        data = pkt.params[1:].hex()
        text = f"WRITE  addr {pkt.params[0]}  data {data}"
    else:
        text = f"{name}  ID {pkt.servo_id}"
    text += "  チェックサム一致" if pkt.cs_ok else "  チェックサム不一致"
    if baud:
        text += f"  {baud} bps"
    return text


def reply_text(master: Packet | None, reply: Packet, echo: bool, us: int) -> str:
    text = f"status {reply.head}"
    text += "  チェックサム一致" if reply.cs_ok else "  チェックサム不一致"
    # アドレス 0 の読み出しなら、サーボが記憶している ID とボーレートが見える。
    if (
        master is not None
        and master.head == 0x02
        and len(master.params) >= 2
        and master.params[0] == 0
        and len(reply.params) >= 7
    ):
        baud_i = reply.params[6]
        bps = SERVO_BAUDS[baud_i] if baud_i < len(SERVO_BAUDS) else 0
        text += f"  サーボ内 ID {reply.params[5]}  サーボ内ボーレート {bps} bps"
    text += f"  {fmt_us(us)}  "
    text += "echo あり" if echo else "echo なし"
    return text


def _num(kv: dict[str, str], key: str) -> int | None:
    raw = kv.get(key)
    if raw is None:
        return None
    try:
        return int(raw, 10)
    except ValueError:
        return None


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


class BusApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SM105BL 通信  /  ATOM S3R + LTC1480")
        self.configure(bg=BG)
        self.minsize(980, 680)
        self.geometry("1180x820")

        self._ports: list[tuple[str, str]] = []
        self.ser: serial.Serial | None = None
        self._tx_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue[tuple[str, dict[str, str]]] = queue.Queue()
        self._rows: list[TraceRow] = []
        self._closing = False
        self.connected = False
        self.armed = False
        self._pos: int | None = None
        self._slider_ready = False
        self._wait_cmd: str | None = None
        self._sent_id = 1
        self._cmd_buttons: list[tk.Button] = []
        self._move_buttons: list[tk.Button] = []
        self.live: dict[str, tk.Label] = {}

        self._build()
        self._refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _event: self._torque_off())
        self.after(50, self._tick)
        self.after(500, self._poll_fb)

    def _build(self) -> None:
        # 上 2/3 が操作とサーボ情報、下 1/3 が往復ログ。ヘッダは高さ固定。
        self.rowconfigure(1, weight=2)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self._build_header()
        self._build_upper()
        self._build_log()
        self._set_buttons()

    def _build_header(self) -> None:
        # ポート列と操作ボタンはヘッダにまとめ、本体の 2:1 分割と混ぜない。
        header = tk.Frame(self, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        top = tk.Frame(header, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text="ポート", bg=BG, fg=MUTED, font=FONT).pack(side="left")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=42, state="readonly")
        self.port_box.pack(side="left", padx=(6, 6))
        self._button(top, "更新", self._refresh_ports).pack(side="left")
        self.connect_btn = self._button(top, "接続", self._toggle_connect)
        self.connect_btn.pack(side="left", padx=(6, 0))
        self.link_var = tk.StringVar(value="未接続")
        self.link_label = tk.Label(top, textvariable=self.link_var, bg=BG, fg=MUTED, font=FONT)
        self.link_label.pack(side="right")

        cmd = tk.Frame(header, bg=BG)
        cmd.pack(fill="x", pady=(4, 0))
        tk.Label(cmd, text="ID", bg=BG, fg=MUTED, font=FONT).pack(side="left")
        self.id_var = tk.StringVar(value="1")
        spin = tk.Spinbox(
            cmd,
            from_=0,
            to=254,
            textvariable=self.id_var,
            width=5,
            font=MONO,
            bg=CARD,
            fg=TEXT,
            buttonbackground=CARD_HI,
            insertbackground=TEXT,
            relief="flat",
        )
        spin.pack(side="left", padx=(6, 10))
        self._cmd_buttons.append(self._button(cmd, "折り返し", self._echo))
        self._cmd_buttons.append(self._button(cmd, "PING", self._ping))
        self._cmd_buttons.append(self._button(cmd, "INFO", self._info))
        self._cmd_buttons.append(self._button(cmd, "ボーレートを探す", self._scan))
        for button in self._cmd_buttons:
            button.pack(side="left", padx=(0, 6))
        self._button(cmd, "消去", self._clear).pack(side="right")

    def _build_upper(self) -> None:
        upper = tk.Frame(self, bg=BG)
        upper.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 6))
        upper.columnconfigure(0, weight=3)
        upper.columnconfigure(1, weight=2)
        upper.rowconfigure(0, weight=1)
        self._build_controls(upper)
        self._build_info(upper)

    def _build_controls(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg=CARD, padx=12, pady=10)
        box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(box, text="操作", bg=CARD, fg=TEXT, font=(FONT[0], 12, "bold")).pack(anchor="w")
        tk.Label(
            box,
            text="トルク ON は今の位置を保持します。バーは離したとき、その位置へ動きます。",
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
        self._spin_row(box, "加速度", self.acc_var, "0 は最大。10 はゆっくり")

        self.arm_btn = self._button(box, "トルク ON（現在位置を保持）", self._arm, fg=GOOD)
        self.arm_btn.pack(fill="x", pady=(8, 8))

        tk.Label(box, text="目標位置（0〜4095、1 周）", bg=CARD, fg=MUTED, font=FONT_SM).pack(anchor="w")
        self.slider_var = tk.DoubleVar(value=2048)
        self.slider = tk.Scale(
            box,
            from_=0,
            to=4095,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=self.slider_var,
            command=self._on_slider,
            bg=CARD,
            fg=TEXT,
            troughcolor=BG,
            activebackground=ACCENT,
            highlightthickness=0,
            sliderlength=28,
            length=280,
        )
        self.slider.pack(fill="x", pady=(4, 0))
        # ドラッグ中は送らない。離したときだけ目標を書く。
        self.slider.bind("<ButtonRelease-1>", self._on_slider_release)
        self.slider_caption = tk.StringVar(value="2048    中点から +0.00°")
        tk.Label(box, textvariable=self.slider_caption, bg=CARD, fg=TEXT, font=MONO).pack(anchor="w", pady=(2, 6))

        jog = tk.Frame(box, bg=CARD)
        jog.pack(fill="x", pady=(4, 4))
        for text, deg in (("−15°", -15), ("−5°", -5), ("+5°", 5), ("+15°", 15)):
            button = self._button(jog, text, lambda d=deg: self._jog(d))
            button.pack(side="left", padx=2, expand=True, fill="x")
            self._move_buttons.append(button)
        self.move_btn = self._button(box, "バーの位置へ動かす", self._move_slider)
        self.move_btn.pack(fill="x", pady=(4, 6))
        self._move_buttons.append(self.move_btn)
        self.off_btn = self._button(box, "トルク OFF", self._torque_off, fg=BAD)
        self.off_btn.pack(fill="x")

    def _build_info(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg=CARD, padx=12, pady=10)
        box.grid(row=0, column=1, sticky="nsew")
        tk.Label(box, text="サーボ", bg=CARD, fg=TEXT, font=(FONT[0], 12, "bold")).pack(anchor="w")
        self.meta_var = tk.StringVar(value="rx=5  tx=6  de=7  /RE=GND  VCC=3.3V")
        tk.Label(box, textvariable=self.meta_var, bg=CARD, fg=MUTED, font=FONT_SM, wraplength=360, justify="left").pack(
            anchor="w", pady=(2, 6)
        )
        self.big_pos = tk.Label(box, text="—", bg=CARD, fg=TEXT, font=MONO_LG)
        self.big_pos.pack(anchor="w")
        self.big_sub = tk.Label(box, text="現在位置", bg=CARD, fg=MUTED, font=FONT_SM)
        self.big_sub.pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(box, bg=CARD)
        grid.pack(fill="both", expand=True)
        names = (
            ("goal", "目標"),
            ("spd", "速度"),
            ("load", "負荷"),
            ("volt", "電圧"),
            ("temp", "温度"),
            ("curr", "電流"),
            ("torque", "トルク"),
            ("moving", "移動"),
            ("status", "状態"),
            ("fw", "ファーム"),
        )
        for index, (key, title) in enumerate(names):
            row, col = divmod(index, 2)
            tk.Label(grid, text=title, bg=CARD, fg=MUTED, font=FONT_SM, anchor="w", width=8).grid(
                row=row, column=col * 2, sticky="w", pady=2
            )
            value = tk.Label(grid, text="—", bg=CARD, fg=TEXT, font=MONO, anchor="w")
            value.grid(row=row, column=col * 2 + 1, sticky="w", padx=(0, 12), pady=2)
            self.live[key] = value

    def _build_log(self) -> None:
        card = tk.Frame(self, bg=CARD)
        card.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        head = tk.Frame(card, bg=CARD)
        head.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 0))
        tk.Label(head, text="RS485 の往復（新しいものが上）", bg=CARD, fg=TEXT, font=FONT).pack(side="left")
        tk.Label(
            head,
            text="灰FF  青ID  白Length  黄命令  緑checksum    地: 緑=echoあり  黄=返事のみ  赤=時間切れ",
            bg=CARD,
            fg=MUTED,
            font=FONT_SM,
        ).pack(side="left", padx=(12, 0))
        self.trace = tk.Text(
            card,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=MONO,
            wrap="none",
            height=8,
            padx=8,
            pady=6,
        )
        yscroll = tk.Scrollbar(card, orient="vertical", command=self.trace.yview)
        xscroll = tk.Scrollbar(card, orient="horizontal", command=self.trace.xview)
        self.trace.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.trace.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")
        xscroll.grid(row=2, column=0, sticky="ew")
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)
        # 無効化すると Windows では背景が灰色になり、コピーもできなくなる。
        self.trace.bind("<Key>", self._readonly_key)
        self.trace.bind("<<Paste>>", lambda _event: "break")

        # 行の地色と、バイト種の文字色は別の tag。地色 tag は文字色を持たない。
        self.trace.tag_configure("good", background="#10261f")
        self.trace.tag_configure("warn", background="#2c2612")
        self.trace.tag_configure("bad", background="#2c1518")
        self.trace.tag_configure("muted", foreground=MUTED)
        self.trace.tag_configure("dir", foreground=ACCENT)
        self.trace.tag_configure("ann", foreground=TEXT)
        self.trace.tag_configure("plain", foreground=TEXT)
        self.trace.tag_configure("hdr", foreground=MUTED)
        self.trace.tag_configure("fid", foreground=ACCENT)
        self.trace.tag_configure("flen", foreground=TEXT)
        self.trace.tag_configure("finst", foreground=WARN)
        self.trace.tag_configure("fparam", foreground=TEXT)
        self.trace.tag_configure("fsum_ok", foreground=GOOD)
        self.trace.tag_configure("fsum_bad", foreground=BAD)
        # 地色より文字色を優先する。地色 tag は background しか持たない。
        for name in ("hdr", "fid", "flen", "finst", "fparam", "fsum_ok", "fsum_bad", "dir", "ann", "plain", "muted"):
            self.trace.tag_raise(name)

    def _spin_row(self, parent: tk.Frame, title: str, variable: tk.StringVar, hint: str) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=title, bg=CARD, fg=MUTED, font=FONT_SM, width=10, anchor="w").pack(side="left")
        tk.Entry(
            row,
            textvariable=variable,
            width=8,
            font=MONO,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
        ).pack(side="left")
        tk.Label(row, text=hint, bg=CARD, fg=MUTED, font=FONT_SM).pack(side="left", padx=(8, 0))

    def _button(self, parent: tk.Misc, text: str, command, fg: str = TEXT) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=CARD_HI,
            fg=fg,
            activebackground=CARD,
            activeforeground=fg,
            relief="flat",
            font=FONT,
            padx=10,
            pady=2,
        )

    def _readonly_key(self, event: tk.Event) -> str | None:
        # コピーと移動だけ通す。編集すると、見ているバイト列が変わる。
        if event.state & 0x4 and event.keysym.lower() in ("c", "a"):
            return None
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"):
            return None
        return "break"

    def _set_buttons(self) -> None:
        state = "normal" if self.connected else "disabled"
        for button in self._cmd_buttons:
            button.configure(state=state)
        self.arm_btn.configure(state=state)
        self.off_btn.configure(state=state)
        move = "normal" if self.connected and self.armed else "disabled"
        for button in self._move_buttons:
            button.configure(state=move)

    def _set_status(self, text: str, color: str) -> None:
        self.link_var.set(text)
        self.link_label.configure(fg=color)

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

    def _servo_id(self) -> int:
        value = int(self.id_var.get(), 10)
        if not 0 <= value <= 254:
            raise ValueError
        return value

    def _toggle_connect(self) -> None:
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        port = self._selected_port()
        if not port:
            messagebox.showwarning("ポート", "ATOM の COM ポートを選んでください。")
            return
        try:
            self._servo_id()
        except ValueError:
            messagebox.showwarning("ID", "ID は 0 から 254 です。254 は 1 台だけの同報です。")
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
        self._set_status(f"{port}  接続中", WARN)
        self._set_buttons()
        # ポートを開いた瞬間にリセットがかかっても、setup が終わるまで待つ。
        self.after(400, self._kickoff)

    def _disconnect(self, send_off: bool = True) -> None:
        # 切る前にトルクを落とす。ウィンドウを閉じたあとも軸が保持しないように。
        if send_off and self.ser is not None:
            self._send("torque 0")
            time.sleep(0.25)
        self.armed = False
        self._wait_cmd = None
        self._slider_ready = False
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
        self.connect_btn.configure(text="接続")
        self._set_status("未接続", MUTED)
        self._set_buttons()

    def _send(self, line: str) -> bool:
        ser = self.ser
        if ser is None:
            return False
        try:
            with self._tx_lock:
                ser.write((line.strip() + "\n").encode("ascii"))
        except serial.SerialException as exc:
            self._set_status(f"送信失敗 {exc}", BAD)
            return False
        return True

    def _send_id(self) -> bool:
        try:
            servo_id = self._servo_id()
        except ValueError:
            messagebox.showwarning("ID", "ID は 0 から 254 です。254 は 1 台だけの同報です。")
            return False
        if not self._send(f"id {servo_id}"):
            return False
        if servo_id != self._sent_id:
            # ファームは宛先が変わると出力中を捨てる。バーはもう一度トルク ON が要る。
            self.armed = False
            self._set_buttons()
        self._sent_id = servo_id
        return True

    def _kickoff(self) -> None:
        if not self.connected:
            return
        self._send_id()
        self._send("echo")
        self._send("hello")
        self._send("ping")

    def _echo(self) -> None:
        self._send("echo")

    def _ping(self) -> None:
        if self._send_id():
            self._send("ping")

    def _info(self) -> None:
        if self._send_id():
            self._send("info")

    def _scan(self) -> None:
        if self._send_id():
            self._send_wait("scan", "scan")

    def _poll_fb(self) -> None:
        # 位置の定期読み。操作の途中には挟まない。ログは同じ 1 行を更新する。
        if self.connected and self._wait_cmd is None and not self._closing:
            self._send("fb")
        if not self._closing:
            self.after(500, self._poll_fb)

    def _motion_args(self) -> tuple[int, int, int] | None:
        try:
            limit = int(self.limit_var.get(), 10)
            speed = int(self.speed_var.get(), 10)
            acc = int(self.acc_var.get(), 10)
        except ValueError:
            messagebox.showwarning("数値", "トルク制限、速度、加速度は整数です。")
            return None
        if not (0 <= limit <= 1000 and 1 <= speed <= 32767 and 0 <= acc <= 254):
            messagebox.showwarning(
                "数値",
                "トルク制限は 0〜1000、速度は 1〜32767、加速度は 0〜254 です。速度 0 は最高速になるので使えません。",
            )
            return None
        return limit, speed, acc

    def _send_wait(self, line: str, cmd: str) -> bool:
        if self._wait_cmd is not None:
            return False
        if not self._send(line):
            return False
        self._wait_cmd = cmd
        return True

    def _finish_wait(self, cmd: str) -> None:
        if self._wait_cmd == cmd:
            self._wait_cmd = None

    def _arm(self) -> None:
        args = self._motion_args()
        if args is None or not self._send_id():
            return
        limit, speed, acc = args
        self._send_wait(f"arm {limit} {speed} {acc}", "arm")

    def _torque_off(self) -> None:
        if self.connected:
            self._send("torque 0")

    def _on_slider(self, value: str) -> None:
        self._show_slider(int(float(value)))

    def _show_slider(self, counts: int) -> None:
        self.slider_caption.set(f"{counts}    中点から {fmt_deg(counts - 2048)}")

    def _on_slider_release(self, _event: tk.Event) -> None:
        if self.armed:
            self._move_slider()

    def _move_slider(self) -> None:
        if not self.armed:
            self._set_status("先にトルク ON", WARN)
            return
        try:
            if self._servo_id() != self._sent_id:
                self._set_status("ID を変えたので、もう一度トルク ON", WARN)
                return
        except ValueError:
            self._set_status("ID は 0 から 254 です", WARN)
            return
        target = int(self.slider_var.get())
        self._move_to(target)

    def _jog(self, deg: float) -> None:
        if not self.armed:
            return
        base = self._pos if self._pos is not None else int(self.slider_var.get())
        target = max(-32767, min(32767, base + counts_from_deg(deg)))
        if 0 <= target <= 4095:
            self.slider_var.set(target)
            self._show_slider(target)
        self._move_to(target)

    def _move_to(self, target: int) -> None:
        if self._pos is not None and abs(target - self._pos) > CONFIRM_COUNTS:
            if not messagebox.askokcancel(
                "大きな移動",
                f"現在 {self._pos} から {target} へ動きます（{fmt_deg(target - self._pos)}）。",
            ):
                return
        self._send_wait(f"move {target}", "move")

    def _sync_slider(self, pos: int) -> None:
        # バーは 1 周分。範囲の外は数値だけ出して、バーは動かさない。
        if 0 <= pos <= 4095:
            self.slider_var.set(pos)
            self._show_slider(pos)

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
            if len(buf) > 16384 and b"\n" not in buf:
                buf = b""
                continue
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                text = raw.decode("ascii", "replace").strip()
                if not text:
                    continue
                kind, kv = parse_line(text)
                self._queue.put((kind, kv))

    def _tick(self) -> None:
        if self._closing:
            return
        while True:
            try:
                kind, kv = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._dispatch(kind, kv)
            except Exception as exc:
                self._push_note(f"表示できない行 {exc}", "bad")
        if not self._closing:
            self.after(50, self._tick)

    def _dispatch(self, kind: str, kv: dict[str, str]) -> None:
        if kind == "bus":
            self._on_bus(kv)
        elif kind == "echo":
            self._on_echo(kv)
        elif kind == "hello":
            self._on_hello(kv)
        elif kind == "info":
            self._on_info(kv)
        elif kind == "fb":
            self._on_fb(kv)
        elif kind == "ok":
            self._on_ok(kv)
        elif kind == "err":
            self._on_err(kv)
        elif kind == "dead":
            self._push_note(f"ポートが落ちました: {kv.get('text', '')}", "bad")
            self._disconnect(send_off=False)
        elif kind == "log":
            self._push_note(kv.get("text", ""), "warn")

    def _on_hello(self, kv: dict[str, str]) -> None:
        if "de" not in kv:
            self._set_status("別ファームです。atom-test で pio run -e rs485 -t upload", BAD)
            self._push_note("hello に de が無い。環境 rs485 を焼いてください", "bad")
            return
        self.meta_var.set(
            f"rx={kv.get('rx')}  tx={kv.get('tx')}  de={kv.get('de')}  "
            f"{kv.get('baud')} bps  ID {kv.get('id')}  self={kv.get('self', '?')}"
        )
        if kv.get("self") == "0":
            self._set_status("ファームのチェックサム自己検査に失敗", BAD)
            self._push_note("self=0  パケット組み立ての自己検査に失敗。焼き直してください", "bad")

    def _on_echo(self, kv: dict[str, str]) -> None:
        tx = parse_hex(kv.get("tx", "")) or b""
        rx = parse_hex(kv.get("rx", ""))
        raw_rx = "" if rx is not None else kv.get("rx", "")
        rx_bytes = rx or b""
        match = rx_bytes == tx and len(tx) > 0
        us = int(kv.get("us", "0") or 0)
        self._push(
            TraceRow(
                kind="echo",
                tone="good" if match else "bad",
                when=time.strftime("%H:%M:%S"),
                tx=tx,
                rx=rx_bytes,
                us=us,
                raw_rx=raw_rx,
            )
        )
        if match:
            self._set_status(f"折り返し一致  {fmt_us(us)}", GOOD)
        else:
            self._set_status("折り返し不一致。DI、RO、DE、3.3V、GND を確認", BAD)

    def _on_bus(self, kv: dict[str, str]) -> None:
        tx = parse_hex(kv.get("tx", "")) or b""
        rx = parse_hex(kv.get("rx", ""))
        raw_rx = "" if rx is not None else kv.get("rx", "")
        rx_bytes = rx or b""
        timeout = kv.get("err") == "timeout"
        echo = kv.get("echo") == "1"
        us = int(kv.get("us", "0") or 0)
        baud = int(kv.get("baud", "0") or 0)
        reply = parse_packet(rx_bytes)
        if timeout or reply is None or not reply.cs_ok:
            tone = "bad"
        elif echo:
            tone = "good"
        else:
            tone = "warn"
        self._push(
            TraceRow(
                kind="bus",
                tone=tone,
                when=time.strftime("%H:%M:%S"),
                tx=tx,
                rx=rx_bytes,
                echo=echo,
                us=us,
                timeout=timeout,
                baud=baud,
                raw_rx=raw_rx,
                extras={"n": kv.get("n", "")},
            ),
            live=is_live_read(tx),
        )

    def _on_info(self, kv: dict[str, str]) -> None:
        if kv.get("ok") != "1":
            self._set_status("INFO を読めませんでした", BAD)
            return
        fw = kv.get("fw", "—")
        self.live["fw"].configure(text=f"{fw}    {kv.get('baud_bps')} bps")
        self._set_status(
            f"INFO  ID {kv.get('id')}  {kv.get('baud_bps')} bps  fw {fw}",
            GOOD,
        )

    def _on_fb(self, kv: dict[str, str]) -> None:
        if kv.get("ok") != "1":
            return
        pos_raw = _num(kv, "pos")
        spd_raw = _num(kv, "spd")
        load_raw = _num(kv, "load")
        goal_raw = _num(kv, "goal")
        if None in (pos_raw, spd_raw, load_raw, goal_raw):
            return
        pos = decode_bit15(pos_raw)
        goal = decode_bit15(goal_raw)
        self._pos = pos
        self._show_position(pos, pos_raw)
        if not self._slider_ready:
            self._sync_slider(pos)
            self._slider_ready = True
        torque = _num(kv, "torque") or 0
        # 保護でサーボが自分から切ることがある。表示だけ出力中のままにしない。
        if self.armed and torque == 0 and self._wait_cmd != "arm":
            self.armed = False
            self._set_buttons()
            self._set_status("サーボがトルクを切りました", WARN)
        volt = _num(kv, "volt") or 0
        temp = _num(kv, "temp") or 0
        curr = _num(kv, "curr") or 0
        status = _num(kv, "status") or 0
        moving = _num(kv, "moving") or 0
        self.live["goal"].configure(text=f"{goal}    {fmt_deg(goal - 2048)}")
        self.live["spd"].configure(text=str(decode_bit15(spd_raw)))
        self.live["load"].configure(text=f"{decode_bit10(load_raw) / 10.0:+.1f}%")
        self.live["volt"].configure(text=f"{volt / 10.0:.1f} V")
        self.live["temp"].configure(text=f"{temp} °C", fg=WARN if temp >= 60 else TEXT)
        self.live["curr"].configure(text=f"{curr * 6.5:.0f} mA")
        self.live["torque"].configure(text=TORQUE_NAME.get(torque, str(torque)))
        self.live["moving"].configure(text="移動中" if moving else "停止")
        self.live["status"].configure(text="0 正常" if status == 0 else str(status), fg=TEXT if status == 0 else BAD)

    def _show_position(self, pos: int, raw: int) -> None:
        self.big_pos.configure(text=fmt_deg(pos - 2048))
        self.big_sub.configure(text=f"中点から    {pos} count    raw {raw}")

    def _on_ok(self, kv: dict[str, str]) -> None:
        cmd = kv.get("cmd", "")
        self._finish_wait(cmd)
        if cmd == "ping":
            st = kv.get("st", "?")
            color = GOOD if st == "0" else WARN
            self._set_status(f"PING 応答  ID {kv.get('id')}  st={st}", color)
        elif cmd == "scan":
            if kv.get("found") == "1":
                self._set_status(f"応答したボーレート {kv.get('baud')} bps。このまま続けます", GOOD)
            else:
                self._set_status("どのボーレートでも応答なし。115200 に戻しました", BAD)
        elif cmd == "arm":
            raw = _num(kv, "pos")
            if raw is not None:
                pos = decode_bit15(raw)
                self._pos = pos
                self._sync_slider(pos)
                self._slider_ready = True
                self._show_position(pos, raw)
            self.armed = True
            self._set_buttons()
            self._set_status(f"トルク ON  保持 {kv.get('pos')}", GOOD)
        elif cmd == "torque" and kv.get("value") == "0":
            self.armed = False
            self._set_buttons()
            self._set_status("トルク OFF", MUTED)
        elif cmd == "move":
            self._set_status(f"目標 {kv.get('pos')}  raw {kv.get('raw')}", GOOD)
        elif cmd == "id":
            self._set_buttons()

    def _on_err(self, kv: dict[str, str]) -> None:
        cmd = kv.get("cmd", "?")
        msg = kv.get("msg", "")
        self._finish_wait(cmd)
        if cmd == "self":
            self._push_note("チェックサム自己検査に失敗", "bad")
        reasons = {
            "torque_off": "トルクが入っていないので、位置は送っていません",
            "timeout": "サーボが応答しません",
            "bad_arg": "範囲外の数値です",
            "use_arm_or_off": "トルク ON は保持ボタンだけが行います",
            "read_pos": "現在位置を読めなかったので、トルクは入れていません",
            "write_goal": "目標の書き込みに失敗したので、切断を試みました",
        }
        self._set_status(reasons.get(msg, f"ERR {cmd} {msg}".strip()), BAD)
        if cmd == "arm":
            self.armed = False
            self._set_buttons()

    def _push_note(self, text: str, tone: str) -> None:
        self._push(TraceRow(kind="note", tone=tone, when=time.strftime("%H:%M:%S"), note=text))

    def _push(self, row: TraceRow, live: bool = False) -> None:
        replaced = False
        if live:
            row.extras["live"] = "1"
            for index, old in enumerate(self._rows):
                if old.extras.get("live") == "1":
                    self._rows[index] = row
                    replaced = True
                    break
        if not replaced:
            self._rows.insert(0, row)
            del self._rows[MAX_ROWS:]
        # 定期読みの更新で、見ている場所を先頭へ引き戻さない。
        self._render(follow=not replaced)

    def _clear(self) -> None:
        self._rows.clear()
        self._render()

    def _render(self, follow: bool = True) -> None:
        view = self.trace.yview()
        self.trace.delete("1.0", "end")
        for row in self._rows:
            if row.kind == "note":
                self._render_note(row)
            elif row.kind == "echo":
                self._render_echo(row)
            else:
                self._render_bus(row)
            self.trace.insert("end", "\n")
        if follow:
            self.trace.see("1.0")
        elif view:
            self.trace.yview_moveto(view[0])

    def _render_note(self, row: TraceRow) -> None:
        start = self._line_start()
        self.trace.insert("end", f"{row.when}  {row.note}", "ann")
        self._close_line(row.tone, start)

    def _render_echo(self, row: TraceRow) -> None:
        match = row.rx == row.tx and len(row.tx) > 0
        self._paint_pair(
            row,
            tx_ann="トランシーバの折り返し  55 AA 55 AA",
            rx_ann=("一致  " if match else "不一致  ") + fmt_us(row.us),
            field=False,
        )

    def _render_bus(self, row: TraceRow) -> None:
        master = parse_packet(row.tx)
        reply = parse_packet(row.rx)
        if master is None:
            tx_ann = "指令がパケットになっていない"
        else:
            tx_ann = master_text(master, row.baud)
        if row.timeout or reply is None:
            n = row.extras.get("n") or str(len(row.rx))
            rx_ann = f"n={n}  {fmt_us(row.us)}  {timeout_reason(row.echo, len(row.rx))}"
        else:
            rx_ann = reply_text(master, reply, row.echo, row.us)
        self._paint_pair(row, tx_ann=tx_ann, rx_ann=rx_ann, field=True)

    def _paint_pair(self, row: TraceRow, tx_ann: str, rx_ann: str, field: bool) -> None:
        self._paint_line(row.tone, row.when, "送信", row.tx, tx_ann, field and parse_packet(row.tx) is not None)
        shown = row.rx if row.raw_rx == "" else b""
        if row.raw_rx:
            self._paint_line(row.tone, "", "受信", b"", rx_ann + "  " + row.raw_rx, False)
            return
        self._paint_line(row.tone, "", "受信", shown, rx_ann, field and parse_packet(shown) is not None)

    def _line_start(self) -> str:
        # 空のときも、直前の行の改行の直後も、次に書く行の先頭になる。
        return self.trace.index("end-1c")

    def _close_line(self, tone: str, start: str) -> None:
        self.trace.insert("end", "\n")
        # 範囲の終わりは含まない。改行の位置を終わりにすると、その行の文字だけに地色が付く。
        self.trace.tag_add(tone, start, self.trace.index("end-1c"))

    def _paint_line(self, tone: str, when: str, direction: str, payload: bytes, ann: str, colored: bool) -> None:
        start = self._line_start()
        clock = f"{when}  " if when else " " * 10
        self.trace.insert("end", clock, "muted")
        self.trace.insert("end", f"{direction}  ", "dir")
        if len(payload) == 0:
            self.trace.insert("end", "（無し）", "muted")
        elif colored:
            self._insert_fields(payload)
        else:
            text = " ".join(f"{b:02X}" for b in payload)
            tag = "fsum_bad" if tone == "bad" else "plain"
            self.trace.insert("end", text, tag)
        self.trace.insert("end", "    " + ann, "ann")
        self._close_line(tone, start)

    def _insert_fields(self, pkt: bytes) -> None:
        view = parse_packet(pkt)
        for index, byte in enumerate(pkt):
            if index < 2:
                tag = "hdr"
            elif index == 2:
                tag = "fid"
            elif index == 3:
                tag = "flen"
            elif index == 4:
                tag = "finst"
            elif index == len(pkt) - 1:
                tag = "fsum_ok" if view is not None and view.cs_ok else "fsum_bad"
            else:
                tag = "fparam"
            gap = " " if index + 1 < len(pkt) else ""
            self.trace.insert("end", f"{byte:02X}{gap}", tag)

    def _on_close(self) -> None:
        self._closing = True
        self._disconnect()
        self.destroy()


def main() -> None:
    _self_check()
    BusApp().mainloop()


if __name__ == "__main__":
    main()
