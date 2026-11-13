#!/usr/bin/env python3
"""
SM105BL と ATOM S3R（LTC1480）の RS485 を、USB の行テキストから見る。

ファーム（atom-test の環境 rs485）がバスを話し、この GUI はバイト列を色分けする。
トルクは入れない。接続しても軸は動かない。

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
MONO = ("Consolas", 11)


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
        self.minsize(880, 560)
        self.geometry("1080x700")

        self._ports: list[tuple[str, str]] = []
        self.ser: serial.Serial | None = None
        self._tx_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue[tuple[str, dict[str, str]]] = queue.Queue()
        self._rows: list[TraceRow] = []
        self._closing = False
        self.connected = False
        self._cmd_buttons: list[tk.Button] = []

        self._build()
        self._refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._tick)

    def _build(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 4))
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

        cmd = tk.Frame(self, bg=BG)
        cmd.pack(fill="x", padx=12, pady=(0, 4))
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

        hint = tk.Frame(self, bg=BG)
        hint.pack(fill="x", padx=12)
        self.meta_var = tk.StringVar(value="rx=5  tx=6  de=7  /RE=GND  VCC=3.3V  115200 8N1")
        tk.Label(hint, textvariable=self.meta_var, bg=BG, fg=MUTED, font=FONT).pack(anchor="w")
        tk.Label(
            hint,
            text="灰 FF FF   青 ID   白 Length   黄 命令/status   緑チェックサム一致   赤不一致    行の地: 緑=echo あり  黄=返事のみ  赤=時間切れ",
            bg=BG,
            fg=MUTED,
            font=("Yu Gothic UI", 9),
        ).pack(anchor="w", pady=(2, 4))

        card = tk.Frame(self, bg=CARD)
        card.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        tk.Label(card, text="RS485 の往復（新しいものが上）", bg=CARD, fg=TEXT, font=FONT).grid(
            row=0, column=0, sticky="w", padx=8, pady=(6, 0)
        )
        self.trace = tk.Text(
            card,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=MONO,
            wrap="none",
            height=22,
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
        self._set_buttons()

    def _button(self, parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=CARD_HI,
            fg=TEXT,
            activebackground=CARD,
            activeforeground=TEXT,
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

    def _disconnect(self) -> None:
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
        return self._send(f"id {servo_id}")

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
            self._send("scan")

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
        elif kind == "ok":
            self._on_ok(kv)
        elif kind == "err":
            self._on_err(kv)
        elif kind == "dead":
            self._push_note(f"ポートが落ちました: {kv.get('text', '')}", "bad")
            self._disconnect()
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
            )
        )

    def _on_info(self, kv: dict[str, str]) -> None:
        if kv.get("ok") != "1":
            self._set_status("INFO を読めませんでした", BAD)
            return
        self._set_status(
            f"INFO  ID {kv.get('id')}  {kv.get('baud_bps')} bps  fw {kv.get('fw')}",
            GOOD,
        )

    def _on_ok(self, kv: dict[str, str]) -> None:
        cmd = kv.get("cmd", "")
        if cmd == "ping":
            st = kv.get("st", "?")
            color = GOOD if st == "0" else WARN
            self._set_status(f"PING 応答  ID {kv.get('id')}  st={st}", color)
        elif cmd == "scan":
            if kv.get("found") == "1":
                self._set_status(f"応答したボーレート {kv.get('baud')} bps。このまま続けます", GOOD)
            else:
                self._set_status("どのボーレートでも応答なし。115200 に戻しました", BAD)

    def _on_err(self, kv: dict[str, str]) -> None:
        cmd = kv.get("cmd", "?")
        msg = kv.get("msg", "")
        if cmd == "self":
            self._push_note("チェックサム自己検査に失敗", "bad")
        self._set_status(f"ERR {cmd} {msg}".strip(), BAD)

    def _push_note(self, text: str, tone: str) -> None:
        self._push(TraceRow(kind="note", tone=tone, when=time.strftime("%H:%M:%S"), note=text))

    def _push(self, row: TraceRow) -> None:
        self._rows.insert(0, row)
        del self._rows[MAX_ROWS:]
        self._render()

    def _clear(self) -> None:
        self._rows.clear()
        self._render()

    def _render(self) -> None:
        self.trace.delete("1.0", "end")
        for row in self._rows:
            if row.kind == "note":
                self._render_note(row)
            elif row.kind == "echo":
                self._render_echo(row)
            else:
                self._render_bus(row)
            self.trace.insert("end", "\n")
        self.trace.see("1.0")

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
