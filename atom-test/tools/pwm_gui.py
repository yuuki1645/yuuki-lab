#!/usr/bin/env python3
"""
RDS51150 の机上試験。ATOM S3R 底面の G5〜G8 へ出す PWM を、スライダで変える。

ファーム（atom-test の環境 pwm）がパルスを出す。この GUI は行テキストで角度を渡す。
接続しただけではパルスは出ない。出力 ON のあいだ、スライダを動かすと幅が変わる。

    0.0° = 500 µs、135.0° = 1500 µs、270.0° = 2500 µs、フレームは 330 Hz。
    角度は 0.1° 単位の整数（1350 = 135.0°）。ファームと同じ式。

起動:
    pip install -r tools/requirements.txt
    python tools/pwm_gui.py

書き込みは atom-test で pio run -e pwm -t upload。既定の hello とは別環境。
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
# ファームの tenthsToPulse / pulseToDuty と同じ。表示が実パルスとずれないようにする。
HZ = 330
BITS = 14
DUTY_MAX = (1 << BITS) - 1
CENTER_X10 = 1350
MIN_X10 = 0
MAX_X10 = 2700
# 脚に付いたままの可動。基板だけの確認では超えても電気的には仕様内。
SAFE_LO = 400
SAFE_HI = 2300
PINS = (5, 6, 7, 8)

BG = "#0e1318"
CARD = "#17202a"
CARD_HI = "#1f2a36"
TEXT = "#e8eef4"
MUTED = "#8b9bb0"
GOOD = "#10ac84"
BAD = "#ee5253"
WARN = "#feca57"
FONT = ("Yu Gothic UI", 10)
FONT_SM = ("Yu Gothic UI", 9)
MONO = ("Consolas", 12, "bold")


def pulse_us(x10: int) -> int:
    """0.1° 単位をハイ時間にする。ファームの整数割り算と同じ。"""
    if x10 < MIN_X10:
        x10 = MIN_X10
    elif x10 > MAX_X10:
        x10 = MAX_X10
    return 500 + (x10 * 2000 + 1350) // 2700


def duty_counts(us: int, hz: int = HZ) -> int:
    """ファームの pulseToDuty と同じ。周期の整数 µs には丸めない。"""
    return (us * hz * DUTY_MAX + 500_000) // 1_000_000


def _self_check() -> None:
    """端と中点が 1 µs でもずれると、オシロの読みと GUI が食い違う。"""
    assert pulse_us(0) == 500
    assert pulse_us(1350) == 1500
    assert pulse_us(2700) == 2500
    assert pulse_us(400) == 796
    assert pulse_us(2300) == 2204
    # 14 ビット、330 Hz。中点と両端。最長 2500 µs は 1 周期（約 3030 µs）に収まる。
    assert duty_counts(500) == 2703
    assert duty_counts(1500) == 8110
    assert duty_counts(2500) == 13516
    assert 2500 * HZ < 1_000_000


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


def parse_line(text: str) -> tuple[str, dict[str, str]]:
    """`@ok k=v ...` を (種別, 辞書) にする。@ が無ければ log。"""
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


def _ints(text: str | None) -> list[int] | None:
    if not text:
        return None
    try:
        return [int(part, 10) for part in text.split(",")]
    except ValueError:
        return None


class PwmApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("RDS51150 PWM  /  ATOM S3R  G5–G8")
        self.configure(bg=BG)
        self.minsize(760, 640)
        self.geometry("860x700")

        self.ser: serial.Serial | None = None
        self._tx_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue[tuple[str, dict[str, str], str]] = queue.Queue()

        self.connected = False
        self.ready = False
        self.output_on = False
        self._hello_deadline = 0.0
        self._closing = False
        self._pending: set[int] = set()
        self._send_job: str | None = None
        self._stat_job: str | None = None
        self._device_us = [0, 0, 0, 0]

        self._build()
        self._refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _event: self._output_off())
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
        self.connect_btn.pack(side="left", padx=(6, 12))
        self.link_var = tk.StringVar(value="未接続")
        self.link_label = tk.Label(top, textvariable=self.link_var, bg=BG, fg=MUTED, font=FONT)
        self.link_label.pack(side="left")
        self.stop_btn = self._button(top, "出力 OFF", self._output_off, fg=BAD)
        self.stop_btn.pack(side="right")

        status = tk.Frame(self, bg=CARD, padx=12, pady=8)
        status.pack(fill="x", padx=12, pady=4)
        self.state_var = tk.StringVar(value="パルス停止")
        self.state_label = tk.Label(status, textvariable=self.state_var, bg=CARD, fg=MUTED, font=MONO)
        self.state_label.pack(side="left")
        self.hz_var = tk.StringVar(value="330 Hz 待ち")
        tk.Label(status, textvariable=self.hz_var, bg=CARD, fg=MUTED, font=FONT).pack(side="right")

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=12, pady=(4, 0))
        self.on_btn = self._button(row, "出力 ON", self._output_on, fg=GOOD)
        self.on_btn.pack(side="left")
        self._button(row, "すべて 135°", self._center_all).pack(side="left", padx=8)
        tk.Label(
            row,
            text="出力 ON のあいだ、スライダに追従してハイ時間が変わる",
            bg=BG,
            fg=MUTED,
            font=FONT_SM,
        ).pack(side="left", padx=8)

        card = tk.Frame(self, bg=CARD, padx=12, pady=10)
        card.pack(fill="x", padx=12, pady=8)
        tk.Label(
            card,
            text="底面のピン。Grove（G1 / G2）ではない。チェックを外したピンは出力 ON でも出さない。",
            bg=CARD,
            fg=MUTED,
            font=FONT_SM,
        ).pack(anchor="w", pady=(0, 6))

        self.x10: list[tk.IntVar] = []
        self.en: list[tk.IntVar] = []
        self.caption: list[tk.Label] = []
        for index, pin in enumerate(PINS):
            line = tk.Frame(card, bg=CARD)
            line.pack(fill="x", pady=4)
            en = tk.IntVar(value=1)
            self.en.append(en)
            tk.Checkbutton(
                line,
                text=f"G{pin}",
                variable=en,
                command=lambda i=index: self._on_enable(i),
                bg=CARD,
                fg=TEXT,
                selectcolor=CARD_HI,
                activebackground=CARD,
                activeforeground=TEXT,
                font=MONO,
                width=5,
                anchor="w",
            ).pack(side="left")
            var = tk.IntVar(value=CENTER_X10)
            self.x10.append(var)
            scale = tk.Scale(
                line,
                from_=MIN_X10,
                to=MAX_X10,
                orient="horizontal",
                resolution=1,
                showvalue=False,
                variable=var,
                bg=CARD,
                fg=TEXT,
                troughcolor=CARD_HI,
                highlightthickness=0,
                command=lambda _value, i=index: self._on_slider(i),
            )
            scale.pack(side="left", fill="x", expand=True, padx=8)
            cap = tk.Label(line, text="", bg=CARD, fg=TEXT, font=MONO, width=28, anchor="w")
            cap.pack(side="left")
            self.caption.append(cap)
            self._paint_caption(index)

        log_card = tk.Frame(self, bg=CARD, padx=8, pady=6)
        log_card.pack(fill="both", expand=True, padx=12, pady=(0, 4))
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

        hint = (
            "信号は 3.3 V、フレームは 330 Hz（約 3.03 ms）。中点 135.0° はハイ 1500 µs。"
            " サーボ電源は基板側。GND は共通。USB の 5 V では RDS51150 は動かない。"
            " 脚に付いたままなら 40°未満と 230°超はメカ端。Esc と正面ボタンでも出力 OFF。"
        )
        tk.Label(self, text=hint, bg=BG, fg=MUTED, font=FONT_SM, anchor="w", wraplength=820, justify="left").pack(
            fill="x", padx=14, pady=(0, 8)
        )

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

    def _paint_caption(self, index: int) -> None:
        x10 = int(self.x10[index].get())
        us = pulse_us(x10)
        mark = ""
        if x10 < SAFE_LO or x10 > SAFE_HI:
            mark = "  端"
        # 出力中だけ、ファームが返した幅を併記する。止まっているあいだの 0 は「出ていない」。
        device = self._device_us[index]
        extra = ""
        if self.output_on and self.en[index].get() and device and device != us:
            extra = f"  装置{device}"
        self.caption[index].configure(text=f"{x10 / 10:.1f}°  {us} µs{mark}{extra}")
        if not self.en[index].get() or not self.output_on:
            color = MUTED
        elif mark:
            color = WARN
        else:
            color = TEXT
        self.caption[index].configure(fg=color)

    def _paint_output(self) -> None:
        if not self.connected:
            self.state_var.set("未接続")
            self.state_label.configure(fg=MUTED)
        elif not self.ready:
            self.state_var.set("ファーム待ち")
            self.state_label.configure(fg=WARN)
        elif self.output_on:
            self.state_var.set("パルス出力中")
            self.state_label.configure(fg=GOOD)
        else:
            self.state_var.set("パルス停止")
            self.state_label.configure(fg=MUTED)
        for index in range(len(PINS)):
            self._paint_caption(index)

    def _log(self, text: str) -> None:
        self.log_text.insert("end", text + "\n")
        # スライダは行が増える。古い行を捨てて、テキストが伸び続けないようにする。
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 200:
            self.log_text.delete("1.0", f"{lines - 200}.0")
        self.log_text.see("end")

    def _refresh_ports(self) -> None:
        ports = list_ports()
        self.port_box["values"] = [label for _device, label in ports]
        self._port_by_label = {label: device for device, label in ports}
        if ports and not self.port_var.get():
            self.port_var.set(ports[0][1])

    def _selected_port(self) -> str | None:
        return self._port_by_label.get(self.port_var.get())

    def _toggle_connect(self) -> None:
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        port = self._selected_port()
        if not port:
            messagebox.showwarning("ポート", "COM ポートを選んでください。")
            return
        try:
            self.ser = open_atom_serial(port)
        except serial.SerialException as exc:
            messagebox.showerror("接続", str(exc))
            return
        self.connected = True
        self.ready = False
        self.output_on = False
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        self.connect_btn.configure(text="切断")
        self.link_var.set(port)
        self.link_label.configure(fg=TEXT)
        self._hello_deadline = time.monotonic() + 2.0
        self._send("hello")
        self._paint_output()
        self._log(f"-- open {port}")

    def _disconnect(self) -> None:
        # 切る前にパルスを止める。ポートを閉じたあとにサーボへ幅が残り続けないように。
        if self.ready:
            self._send("out 0")
            time.sleep(0.05)
        self._stop.set()
        ser = self.ser
        self.ser = None
        if ser is not None:
            try:
                ser.close()
            except serial.SerialException:
                pass
        self.connected = False
        self.ready = False
        self.output_on = False
        self._device_us = [0, 0, 0, 0]
        if self._stat_job is not None:
            self.after_cancel(self._stat_job)
            self._stat_job = None
        self.connect_btn.configure(text="接続")
        self.link_var.set("未接続")
        self.link_label.configure(fg=MUTED)
        self.hz_var.set("330 Hz 待ち")
        self._paint_output()

    def _reader(self) -> None:
        buf = bytearray()
        while not self._stop.is_set():
            ser = self.ser
            if ser is None:
                break
            try:
                data = ser.read(256)
            except serial.SerialException:
                self._queue.put(("dead", {}, ""))
                break
            if not data:
                continue
            buf.extend(data)
            while b"\n" in buf:
                raw, _, buf = buf.partition(b"\n")
                text = raw.decode("utf-8", "replace").strip()
                if not text:
                    continue
                kind, kv = parse_line(text)
                self._queue.put((kind, kv, text))

    def _send(self, line: str) -> bool:
        ser = self.ser
        if ser is None:
            return False
        try:
            with self._tx_lock:
                ser.write((line + "\n").encode("ascii"))
        except serial.SerialException:
            return False
        return True

    def _on_slider(self, index: int) -> None:
        self._paint_caption(index)
        if not self.ready:
            return
        # Scale はドラッグ中に何度も来る。最新の角度だけを少し遅れて送る。
        self._pending.add(index)
        if self._send_job is None:
            self._send_job = self.after(30, self._flush_deg)

    def _flush_deg(self) -> None:
        self._send_job = None
        if not self.ready:
            self._pending.clear()
            return
        for index in sorted(self._pending):
            self._send(f"deg {index} {int(self.x10[index].get())}")
        self._pending.clear()

    def _on_enable(self, index: int) -> None:
        self._paint_caption(index)
        if self.ready:
            self._send(f"en {index} {1 if self.en[index].get() else 0}")

    def _push_targets(self) -> None:
        """出力を入れる前に、今のスライダをファームへ揃える。"""
        for index in range(len(PINS)):
            self._send(f"en {index} {1 if self.en[index].get() else 0}")
            self._send(f"deg {index} {int(self.x10[index].get())}")

    def _output_on(self) -> None:
        if not self.ready:
            return
        self._push_targets()
        self._send("out 1")

    def _output_off(self) -> None:
        if self.ready:
            self._send("out 0")

    def _center_all(self) -> None:
        for var in self.x10:
            var.set(CENTER_X10)
        # IntVar 経由だと Scale の command が各チャンネルで走る。未接続なら表示だけ。

    def _schedule_stat(self) -> None:
        if not self.ready or self._closing:
            return
        self._send("stat")
        self._stat_job = self.after(1000, self._schedule_stat)

    def _tick(self) -> None:
        if self.connected and not self.ready and self._hello_deadline and time.monotonic() > self._hello_deadline:
            self._hello_deadline = 0.0
            self.link_var.set("応答なし。環境 pwm を焼いたか確認")
            self.link_label.configure(fg=BAD)
        while True:
            try:
                kind, kv, raw = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "dead":
                self._log("-- port lost")
                self._disconnect()
                break
            self._on_line(kind, kv, raw)
        if not self._closing:
            self.after(50, self._tick)

    def _on_line(self, kind: str, kv: dict[str, str], raw: str) -> None:
        # stat は 1 秒ごと。ログに残すとスライダの行が流れる。
        # deg はドラッグ中に連続する。幅はスライダ横に出すので、ログには残さない。
        if kind not in ("stat",) and not (kind == "ok" and kv.get("cmd") == "deg"):
            self._log(raw)
        if kind == "hello":
            self._on_hello(kv)
        elif kind == "ok":
            self._on_ok(kv)
        elif kind == "err":
            self.link_var.set(f"エラー {kv.get('cmd', '?')} {kv.get('msg', '')}")
            self.link_label.configure(fg=BAD)
        elif kind == "stat":
            self._on_stat(kv)

    def _on_hello(self, kv: dict[str, str]) -> None:
        if kv.get("name") != "atom-test-pwm":
            self.link_var.set("pwm ファームではない")
            self.link_label.configure(fg=BAD)
            return
        # 起動時の @hello と、こちらが送った hello の応答が両方届く。初期化は一度だけ。
        first = not self.ready
        self.ready = True
        self._hello_deadline = 0.0
        hz = kv.get("hz", "?")
        bits = kv.get("bits", "?")
        self.hz_var.set(f"{hz} Hz / {bits} bit / 500–2500 µs")
        self.link_var.set("接続")
        self.link_label.configure(fg=GOOD)
        if not first:
            return
        # 開き直したときは、前回のパルスが残っていても一度止める。
        self._send("out 0")
        self._push_targets()
        self.output_on = False
        self._paint_output()
        self._schedule_stat()

    def _on_ok(self, kv: dict[str, str]) -> None:
        cmd = kv.get("cmd")
        if cmd == "out":
            self.output_on = kv.get("value") == "1"
            if kv.get("src") == "button":
                self.link_var.set("正面ボタンで停止")
                self.link_label.configure(fg=WARN)
            elif self.output_on:
                self.link_var.set("出力中")
                self.link_label.configure(fg=GOOD)
            else:
                self.link_var.set("停止")
                self.link_label.configure(fg=TEXT)
            if not self.output_on:
                self._device_us = [0, 0, 0, 0]
            self._paint_output()
        elif cmd == "deg":
            try:
                index = int(kv.get("ch", "-1"))
                us = int(kv.get("us", "0"))
            except ValueError:
                return
            if 0 <= index < len(self._device_us) and kv.get("out") == "1" and kv.get("en") == "1":
                self._device_us[index] = us
                self._paint_caption(index)

    def _on_stat(self, kv: dict[str, str]) -> None:
        # チェックは GUI が持つ。stat で戻すと、クリック直後の 1 秒で表示がひっくり返る。
        self.output_on = kv.get("out") == "1"
        us = _ints(kv.get("us"))
        if us and len(us) == len(PINS):
            self._device_us = us
        elif not self.output_on:
            self._device_us = [0, 0, 0, 0]
        self._paint_output()

    def _on_close(self) -> None:
        self._closing = True
        self._disconnect()
        self.destroy()


def main() -> None:
    _self_check()
    app = PwmApp()
    app.mainloop()


if __name__ == "__main__":
    main()
