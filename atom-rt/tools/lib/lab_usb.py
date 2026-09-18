"""
ATOM 1 台の USB セッション（ライブラリ。直接起動しない）。

裏スレッドでバイナリフレームを読み、Tk は pump() で解釈結果だけ見る。
起動 WAV も HELLO〜スキャン健全性の判定もここ。
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import serial
import serial.tools.list_ports

from . import rt_usb_proto as proto
from .lab_const import (
    BAUD,
    BOOT_SOUND_GAP_S,
    BOOT_WAV,
    GREEN_FRAME_NEED,
    GREEN_WAV,
    EVENTS_MAX,
    JOINTS,
    MAG_LABEL,
    NODES_PATH,
)
from .lab_model import (
    FootRoute,
    Frame,
    JointRoute,
    ScanNode,
    default_foot,
    default_routes,
    describe_i2c_fails,
    foot_from_bin,
    frame_from_telem,
    joint_en_mask,
    route_from_bin,
    scan_node_from_bin,
)

# 同じ欠測が続くときは、この間隔で 1 行にまとめる（毎フレームの累計連打を止める）
_I2C_NOTE_S = 2.0


def _hello_fw_ver(text: str) -> int:
    """HELLO `rt-usb ver=11 lab ...` から USB プロトコル版を取る。取れなければ 0。"""
    marker = "ver="
    i = text.find(marker)
    if i < 0:
        return 0
    digits = []
    for ch in text[i + len(marker) :]:
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    if not digits:
        return 0
    return int("".join(digits))

# Windows 標準。WAV を追加依存なしで再生する（ATOMS3R 移行までの暫定）
try:
    import winsound
except ImportError:
    winsound = None  # type: ignore[assignment]


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


def is_atom_hwid(hwid: str | None) -> bool:
    """Espressif USB VID 303A（ATOMS3 系）かどうか。"""
    return "303A" in (hwid or "")


def list_ports() -> list[tuple[str, str]]:
    """(COM, 説明) ATOMS3(303A) を先頭に。"""
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=lambda p: (0 if is_atom_hwid(p.hwid) else 1, p.device))
    return [(p.device, p.description or "") for p in ports]


def first_atom_port() -> str | None:
    """接続対象にする 1 台目の ATOM COM。303A が無ければ None。"""
    atoms = [p for p in serial.tools.list_ports.comports() if is_atom_hwid(p.hwid)]
    if not atoms:
        return None
    atoms.sort(key=lambda p: p.device)
    return atoms[0].device


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


def open_atom_serial(port: str) -> serial.Serial:
    """
    ATOM の USB-Serial-JTAG を開く。

    pyserial の既定は open 時に DTR を立て、再接続のたびにリセットする。
    NVS 書き込み中のそのリセットが `en` を消していた。
    """
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
        # NVS 一覧は欠けたら「未読取」のままなので、キューが混んでいても捨てない。
        q = self.out.qsize()
        if kind.startswith("nvs_"):
            self.out.put((self.port, kind, payload))
            return
        limit = 500 if kind == "frame" else 200
        if q < limit:
            self.out.put((self.port, kind, payload))

    def _run(self) -> None:
        try:
            ser = open_atom_serial(self.port)
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
                    # マップチャンクは CDC が溢れないよう間隔を空ける（30ms では 32/191 で落ちた）
                    if len(msg) >= 3 and msg[2] == proto.CMD_MAPCHUNK:
                        time.sleep(0.12)
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
            n = payload[0] if payload else 0
            self._put("scan_begin", n)
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
            got = proto.decode_prof(payload)
            if got is not None:
                rs, foot, has_en = got
                self._put(
                    "prof",
                    ([route_from_bin(r) for r in rs], foot_from_bin(foot), bool(has_en)),
                )
            return
        if msg_type == proto.MSG_MAP_CHUNK:
            return
        if msg_type == proto.MSG_NVS_BEGIN:
            self._put("nvs_begin", None)
            return
        if msg_type == proto.MSG_NVS_ENTRY:
            e = proto.decode_nvs_entry(payload)
            if e is not None:
                self._put("nvs_entry", e)
            return
        if msg_type == proto.MSG_NVS_DATA:
            d = proto.decode_nvs_data(payload)
            if d is not None:
                self._put("nvs_data", d)
            return
        if msg_type == proto.MSG_NVS_END:
            self._put("nvs_end", proto.decode_nvs_end(payload))
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


class AtomSession:
    """1 COM の接続状態。Tk は pump() でキューを空にする。"""

    def __init__(self, port: str) -> None:
        self.port = port
        self.name = ""
        self.worker: AtomWorker | None = None
        self.q: queue.Queue = queue.Queue()
        self.connected = False
        self.hello = ""
        self.fw_ver = 0
        self._pending_jen: int | None = None
        self._pending_fen: int | None = None
        self.mode = "lab"
        self.out_mask = 0
        self.nodes: list[ScanNode] = []
        self._scan_acc: list[ScanNode] = []
        self._scan_expect = 0
        self._scan_open = False
        self.routes: list[JointRoute] = default_routes()
        self.foot: FootRoute = default_foot()
        self.map_points: list[tuple[float, float]] = []
        self.map_ch = 0
        self.cal_status = ""
        self.nvs_entries: list[dict[str, object]] = []
        self.nvs_bytes = 0
        self.nvs_ok = False
        self._nvs_acc: list[dict[str, object]] = []
        self.events: deque[str] = deque(maxlen=EVENTS_MAX)
        self.event_seq = 0
        self._event_pending: list[dict[str, object]] = []
        self.history: deque[Frame] = deque(maxlen=400)
        self.flash_until = 0.0
        self.last_frame: Frame | None = None
        self._last_ok: list[bool | None] = [None] * JOINTS
        self._last_i2c = 0
        self._i2c_fail_sig: tuple[str, ...] = ()
        self._i2c_note_at = 0.0
        self._i2c_err_at_note = 0
        self.log_fp = None
        # PC 側電流監視が一度発火したら、下がるまで再発火しない
        self.amp_tripped = False
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
        self._scan_acc = []
        self._scan_expect = 0
        self._scan_open = False
        self._post_hello_frames = 0
        self._startup_overrun = False
        self._startup_overcurrent = False
        self._i2c_err_at_hello = None
        self.fw_ver = 0
        self.amp_tripped = False
        self._i2c_fail_sig = ()
        self._i2c_note_at = 0.0
        self._i2c_err_at_note = 0

    def send(self, data: bytes) -> None:
        if self.worker is not None:
            self.worker.send(data)

    def send_map(self, ch: int, points: list[tuple[float, float]]) -> None:
        """校正点をチャンクに分けて送る。間隔は AtomWorker が空ける。"""
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
        """時刻付き1行をリング末尾へ積む。Hub へは seq 付き追記で届ける。"""
        stamp = time.strftime("%H:%M:%S")
        line = f"{stamp}  {text}"
        self.event_seq += 1
        self.events.append(line)
        self._event_pending.append({"seq": self.event_seq, "text": line})

    def drain_event_pending(self) -> list[dict[str, object]]:
        """未送信の追記バッチを取り出す。接続前の分は hello スナップショットで補う。"""
        pending = self._event_pending
        if not pending:
            return []
        self._event_pending = []
        return pending

    def pump(self) -> None:
        try:
            while True:
                port, kind, payload = self.q.get_nowait()
                if port != self.port:
                    continue
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self._maybe_play_green()

    def _handle(self, kind: str, payload: object) -> None:
        if kind == "status":
            self.connected = payload == "接続"
            self.note(str(payload))
            if self.connected:
                self.send(proto.cmd_ping())
                if not self._got_scan:
                    self.send(proto.cmd_scan())
                self.send(proto.cmd_prof_get())
        elif kind == "error":
            self.connected = False
            self.note(f"ERROR  {payload}")
            self._green_sound_failed = True
        elif kind == "hello":
            self.hello = str(payload)
            self.fw_ver = _hello_fw_ver(self.hello)
            self.note(str(payload))
            self._got_hello = True
            if not self._boot_sound_played:
                self._boot_sound_played = True
                self._boot_sound_at = time.time()
                if play_boot_sound():
                    self.note(f"起動音  {BOOT_WAV.name}")
                else:
                    self.note(f"起動音なし  {BOOT_WAV.name}")
            # ping の HELLO では取り直さない。接続時の prof_get と PUT ダンプを上書きしない
        elif kind == "scan_begin":
            self._scan_acc = []
            self._scan_expect = int(payload) if isinstance(payload, int) else 0
            self._scan_open = True
        elif kind == "node":
            if isinstance(payload, ScanNode) and self._scan_open:
                self._scan_acc.append(payload)
        elif kind == "scan_end":
            got = len(self._scan_acc)
            if not self._scan_open or got != self._scan_expect:
                self.note(f"スキャン不完全  {got}/{self._scan_expect} 破棄")
                self._scan_acc = []
                self._scan_open = False
            else:
                self.nodes = list(self._scan_acc)
                self._got_scan = True
                self._scan_open = False
                self.note(f"スキャン {got} ノード")
                self._maybe_play_green()
        elif kind == "prof":
            routes = None
            foot = None
            has_en = True
            if isinstance(payload, tuple) and len(payload) >= 2:
                routes, foot = payload[0], payload[1]
                if len(payload) >= 3:
                    has_en = bool(payload[2])
            elif isinstance(payload, list):
                routes = payload
            if isinstance(routes, list) and routes:
                merged = default_routes()
                for i, r in enumerate(routes[:JOINTS]):
                    merged[i] = r
                # 旧ダンプは有効マスクが無く decode が全オンにする。手元の無効化を潰さない
                if not has_en:
                    for i, r in enumerate(merged):
                        if i < len(self.routes):
                            r.enabled = self.routes[i].enabled
                    if isinstance(foot, FootRoute):
                        foot.enabled = self.foot.enabled
                self.routes = merged
                if isinstance(foot, FootRoute):
                    self.foot = foot
                jen = joint_en_mask(self.routes)
                fen = int(bool(self.foot.enabled))
                extra = "" if has_en else " マスク無し"
                pending = self._pending_jen
                pending_fen = self._pending_fen
                self._pending_jen = None
                self._pending_fen = None
                if pending is not None and has_en and (jen != pending or fen != int(pending_fen or 0)):
                    extra += f" 不一致 送信jen=0x{pending:02X} fen={int(pending_fen or 0)}"
                self.note(f"プロファイル受信  {len(routes)} 軸  jen=0x{jen:02X} fen={fen}{extra}")
            else:
                self.note("プロファイル不完全")
        elif kind == "nvs_begin":
            self._nvs_acc = []
            self.nvs_ok = False
            self.note("NVS 読み取り開始")
        elif kind == "nvs_entry":
            if isinstance(payload, proto.NvsEntryBin):
                self._nvs_acc.append(
                    {
                        "ns": payload.ns,
                        "key": payload.key,
                        "type": payload.type,
                        "size": payload.size,
                        "data_hex": "",
                    }
                )
        elif kind == "nvs_data":
            if isinstance(payload, proto.NvsDataChunk) and self._nvs_acc:
                last = self._nvs_acc[-1]
                if last.get("ns") == payload.ns and last.get("key") == payload.key:
                    prev = str(last.get("data_hex") or "")
                    last["data_hex"] = prev + payload.data.hex()
        elif kind == "nvs_end":
            self.nvs_entries = list(self._nvs_acc)
            self._nvs_acc = []
            n = int(payload[0]) if isinstance(payload, tuple) and payload else len(self.nvs_entries)
            nb = int(payload[1]) if isinstance(payload, tuple) and len(payload) > 1 else 0
            self.nvs_bytes = nb
            self.nvs_ok = True
            self.note(f"NVS  {n} キー  {nb}B")
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
        self._note_i2c(f)
        self._last_i2c = f.i2c_err
        if f.overrun:
            self.note(f"overrun seq={f.seq} loop={f.loop_us}us")

    def _note_i2c(self, f: Frame) -> None:
        """
        i2c_err の内訳をイベントに出す。

        累計だけだと机上で誰が NACK しているか分からないので、
        プロファイル上読むべきなのに落ちている相手を列挙する。
        相手が変わったときと、同じ相手が 2 秒以上続くときだけ書く。
        """
        fails = describe_i2c_fails(f, self.routes, self.foot)
        sig = tuple(fails)
        now = time.time()
        changed = sig != self._i2c_fail_sig
        grew = f.i2c_err > self._last_i2c
        if changed:
            if fails:
                detail = " / ".join(fails)
                self.note(f"I2C 欠測  {detail}")
            elif self._i2c_fail_sig:
                self.note("I2C 欠測なし（回復または無効化）")
            self._i2c_fail_sig = sig
            self._i2c_note_at = now
            self._i2c_err_at_note = f.i2c_err
            return
        if fails and grew and (now - self._i2c_note_at) >= _I2C_NOTE_S:
            n = f.i2c_err - self._i2c_err_at_note
            detail = " / ".join(fails)
            self.note(f"I2C 継続  +{n}  累計{f.i2c_err}  {detail}")
            self._i2c_note_at = now
            self._i2c_err_at_note = f.i2c_err

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
        has_as = any(n.kind == "as5600" for n in self.nodes)
        has_ina = any(n.kind == "ina226" for n in self.nodes)
        if has_as:
            if not any(f.as_ok):
                return False, "AS5600 が読めない"
            if any(code in (1, 4) for code in f.mag if code != 255):
                bad = [i for i, c in enumerate(f.mag) if c in (1, 4)]
                if bad:
                    return False, f"AS5600 磁石異常 ch{bad}"
        if has_ina:
            assigned = [i for i, r in enumerate(self.routes[:JOINTS]) if r.ina_addr]
            if assigned and not any(f.ina_ok[i] for i in assigned if i < len(f.ina_ok)):
                return False, "INA226 が読めない"
            if not assigned and not any(f.ina_ok):
                return False, "INA226 が読めない"
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
