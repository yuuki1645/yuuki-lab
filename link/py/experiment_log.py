"""
CoreS3（USB ver 15）の実験記録。

サブ PC の lab_debug が HELLO を受けたあと、切断までセンサー・指令・イベントを
ローカル SSD（data_root）へ書く。開いているファイルは NAS へ送らない。
閉じた断片だけを archive_root へコピーし、失敗した分は印を残して次の起動で再送する。

設定の実体はリポジトリの外:
  Path.home() / ".yuuki-lab" / "storage.yaml"
サンプルは link/storage.example.yaml。このモジュールは保管先のパスをログに出さない。
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import secrets
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# 実験中の正本は SSD。この間隔で flush し、落ちて失うのは直前のこの秒数だけにする。
FLUSH_SEC = 1.5
# 閉じた断片を NAS へ出せる間隔。開いたままのファイルは対象にしない。
ROTATE_SEC = 60.0
FORMAT_ID = "core_take_v1"
SCHEMA_FILE = "schema.md"

# プロセス内で 1 つ。未接続のあいだは作らない（shared が最初の ver 15 で作る）。
_SHARED: ExperimentLog | None = None


@dataclass
class StoragePaths:
    """記録プロセスが見る 2 つの根。archive_root が None なら SSD だけ。"""

    data_root: Path
    archive_root: Path | None


@dataclass
class BeginResult:
    ok: bool
    reason: str


def default_storage_path() -> Path:
    """ログイン中のユーザーだけが読む設定。リポジトリには置かない。"""
    return Path.home() / ".yuuki-lab" / "storage.yaml"


def schema_source() -> Path:
    """欄の説明の正本。take へは schema.md としてコピーする。"""
    return Path(__file__).resolve().parent.parent / "schema" / f"{FORMAT_ID}.md"


def _parse_storage_text(text: str) -> dict[str, str]:
    """storage.yaml の key: value だけ読む。PyYAML には依存しない。"""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def load_storage(path: Path | None = None) -> StoragePaths | None:
    """設定が無い、または data_root が空なら None。呼び出し側は記録せず続行する。"""
    file = path if path is not None else default_storage_path()
    if not file.is_file():
        return None
    try:
        parsed = _parse_storage_text(file.read_text(encoding="utf-8-sig"))
    except OSError:
        return None
    raw_data = parsed.get("data_root", "").strip()
    if not raw_data:
        return None
    raw_archive = parsed.get("archive_root", "").strip()
    # resolve しない。切断中の NAS ドライブで例外にしない。
    return StoragePaths(
        data_root=Path(raw_data).expanduser(),
        archive_root=Path(raw_archive).expanduser() if raw_archive else None,
    )


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _pending_marker(src: Path) -> Path:
    """閉じたファイルの隣に置く再送印。中身は空。"""
    return Path(str(src) + ".pending")


@dataclass
class _Take:
    """1 回の USB 接続。フォルダ名はローカル時刻の時分秒。"""

    port: str
    directory: Path
    relative: Path
    meta: dict[str, Any]
    part_index: int
    part_opened: float
    last_flush: float
    last_seq: int | None
    samples: int
    part_bytes: int
    sensors: Any
    commands: Any
    events: Any
    sensor_path: Path
    command_path: Path
    event_path: Path


class ExperimentLog:
    """1 プロセスに 1 つ。USB スレッドは待たせず、コピーは別スレッド。"""

    def __init__(
        self,
        paths: StoragePaths | None,
        *,
        flush_sec: float = FLUSH_SEC,
        rotate_sec: float = ROTATE_SEC,
        copy_async: bool = True,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.paths = paths
        self.flush_sec = flush_sec
        self.rotate_sec = rotate_sec
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._take: _Take | None = None
        self._warned_at: dict[str, float] = {}
        self._q: queue.Queue[Path | None] = queue.Queue()
        self._async = bool(copy_async and paths is not None and paths.archive_root is not None)
        self._thread: threading.Thread | None = None
        if self._async:
            self._thread = threading.Thread(
                target=self._copy_loop,
                name="experiment-archive",
                daemon=True,
            )
            self._thread.start()
        self.catch_up()

    def begin(self, port: str, hello: str, fw_ver: int) -> BeginResult:
        """take を開く。同じポートの HELLO 繰り返しでは新しいフォルダを作らない。"""
        with self._lock:
            if self.paths is None:
                return BeginResult(False, "no_config")
            if self._take is not None:
                if self._take.port == port:
                    return BeginResult(True, "already")
                return BeginResult(False, "busy")
            now = datetime.now().astimezone()
            directory = self._allocate_dir(now)
            try:
                directory.mkdir(parents=True, exist_ok=False)
            except OSError:
                return BeginResult(False, "mkdir_failed")
            relative = directory.relative_to(self.paths.data_root)
            take_id = directory.name
            meta: dict[str, Any] = {
                "format_id": FORMAT_ID,
                "take_id": take_id,
                "started_at": now.isoformat(timespec="milliseconds"),
                "started_unix": time.time(),
                "ended_at": None,
                "ended_unix": None,
                "recording": True,
                "notes": "",
                "hello": hello,
                "port": port,
                "fw_ver": int(fw_ver),
                "sample_count": 0,
                "stop_reason": "",
                "schema": "",
                "open_parts": [],
            }
            take = _Take(
                port=port,
                directory=directory,
                relative=relative,
                meta=meta,
                part_index=0,
                part_opened=self._clock(),
                last_flush=self._clock(),
                last_seq=None,
                samples=0,
                part_bytes=0,
                sensors=None,
                commands=None,
                events=None,
                sensor_path=directory / "sensors" / "part-000.jsonl",
                command_path=directory / "commands" / "part-000.jsonl",
                event_path=directory / "events" / "part-000.log",
            )
            self._take = take
            self._open_parts_locked(take)
            # 説明は追記しない。開いた瞬間に閉じたファイルとして置く。
            if self._install_schema(take):
                self._enqueue(take.directory / SCHEMA_FILE, touch=True)
            else:
                self._write_event_locked(take, "説明ファイルなし")
            self._write_event_locked(take, f"記録開始  {relative.as_posix()}")
            self._write_meta_locked(take)
            print(f"実験記録開始  {relative.as_posix()}")
            return BeginResult(True, "started")

    def append_frame(self, port: str, frame: dict[str, Any]) -> None:
        """テレメトリ 1 行。同じ seq は捨てる。"""
        with self._lock:
            take = self._accept(port)
            if take is None or take.sensors is None:
                return
            seq = frame.get("seq")
            if isinstance(seq, int) and seq == take.last_seq:
                return
            if isinstance(seq, int):
                take.last_seq = seq
            self._write_line(take.sensors, frame)
            take.samples += 1
            take.meta["sample_count"] = take.samples
            self._after_write_locked(take)

    def append_command(self, port: str, command: dict[str, Any]) -> None:
        """PC からボードへ出した指令 1 件。"""
        with self._lock:
            take = self._accept(port)
            if take is None or take.commands is None:
                return
            body = dict(command)
            body.setdefault("t", time.time())
            self._write_line(take.commands, body)
            self._after_write_locked(take)

    def append_event(self, port: str, text: str) -> None:
        """画面のイベント行。日付つきで残し、センサーの jsonl には混ぜない。"""
        with self._lock:
            take = self._accept(port)
            if take is None:
                return
            self._write_event_locked(take, text)
            self._after_write_locked(take)

    def end(self, port: str, reason: str) -> None:
        """このポートの take を閉じる。別ポートの切断では閉じない。"""
        with self._lock:
            if self._take is None or self._take.port != port:
                return
            self._finish_locked(reason)

    def end_open(self, reason: str) -> None:
        """開いている take があれば閉じる。プロセス終了用。"""
        with self._lock:
            if self._take is None:
                return
            self._finish_locked(reason)

    def catch_up(self) -> None:
        """前回閉じきれなかった take と、未コピーの印を送る。"""
        if self.paths is None or not self.paths.data_root.is_dir():
            return
        for meta_path in self._interrupted_metas(self.paths.data_root):
            self._seal_interrupted(meta_path)
        if self.paths.archive_root is None:
            return
        seen: set[Path] = set()
        for marker in self.paths.data_root.rglob("*.pending"):
            if not marker.is_file() or not marker.name.endswith(".pending"):
                continue
            src = Path(str(marker)[: -len(".pending")])
            if src in seen or not src.is_file():
                continue
            seen.add(src)
            self._enqueue(src, touch=False)

    def _install_schema(self, take: _Take) -> bool:
        """正本を take の schema.md へコピーする。無いときは記録自体は続ける。"""
        src = schema_source()
        if not src.is_file():
            return False
        dest = take.directory / SCHEMA_FILE
        try:
            shutil.copyfile(src, dest)
        except OSError:
            return False
        take.meta["schema"] = SCHEMA_FILE
        return True

    def _accept(self, port: str) -> _Take | None:
        take = self._take
        if take is None or take.port != port:
            return None
        return take

    def _allocate_dir(self, now: datetime) -> Path:
        assert self.paths is not None
        day = (
            self.paths.data_root
            / f"{now.year:04d}"
            / f"{now.month:02d}"
            / f"{now.day:02d}"
        )
        base = now.strftime("%H%M%S")
        candidate = day / base
        if not candidate.exists():
            return candidate
        for _ in range(8):
            alt = day / f"{base}_{secrets.token_hex(2)}"
            if not alt.exists():
                return alt
        return day / f"{base}_{secrets.token_hex(4)}"

    def _open_parts_locked(self, take: _Take) -> None:
        idx = f"{take.part_index:03d}"
        take.sensor_path = take.directory / "sensors" / f"part-{idx}.jsonl"
        take.command_path = take.directory / "commands" / f"part-{idx}.jsonl"
        take.event_path = take.directory / "events" / f"part-{idx}.log"
        for path in (take.sensor_path, take.command_path, take.event_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        # 行バッファにしない。FLUSH_SEC までメモリに溜める。
        take.sensors = take.sensor_path.open("a", encoding="utf-8", buffering=64 * 1024)
        take.commands = take.command_path.open("a", encoding="utf-8", buffering=64 * 1024)
        take.events = take.event_path.open("a", encoding="utf-8", buffering=64 * 1024)
        take.part_opened = self._clock()
        take.part_bytes = 0
        take.meta["open_parts"] = [
            take.sensor_path.relative_to(take.directory).as_posix(),
            take.command_path.relative_to(take.directory).as_posix(),
            take.event_path.relative_to(take.directory).as_posix(),
        ]

    def _write_line(self, fp: Any, obj: dict[str, Any]) -> None:
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
        fp.write(data)

    def _write_event_locked(self, take: _Take, text: str) -> None:
        if take.events is None:
            return
        flat = text.replace("\r", " ").replace("\n", " ")
        line = f"{_iso_now()}  {flat}\n"
        take.events.write(line)
        take.part_bytes += len(line.encode("utf-8"))

    def _after_write_locked(self, take: _Take) -> None:
        # json 行のバイト数は厳密でなくてよい。回転の有無だけ見る。
        take.part_bytes += 1
        now = self._clock()
        if now - take.last_flush >= self.flush_sec:
            self._flush_locked(take)
            take.last_flush = now
        if take.part_bytes > 0 and now - take.part_opened >= self.rotate_sec:
            self._rotate_locked(take)

    def _flush_locked(self, take: _Take) -> None:
        for fp in (take.sensors, take.commands, take.events):
            if fp is None:
                continue
            fp.flush()
            try:
                os.fsync(fp.fileno())
            except OSError:
                pass
        self._write_meta_locked(take)

    def _rotate_locked(self, take: _Take) -> None:
        self._close_parts_locked(take)
        take.part_index += 1
        self._open_parts_locked(take)
        self._write_meta_locked(take)

    def _close_parts_locked(self, take: _Take) -> None:
        """開いている 3 ファイルを閉じ、中身があるものだけコピー待ちにする。"""
        pairs = (
            (take.sensors, take.sensor_path),
            (take.commands, take.command_path),
            (take.events, take.event_path),
        )
        take.sensors = None
        take.commands = None
        take.events = None
        for fp, path in pairs:
            if fp is None:
                continue
            try:
                fp.flush()
                os.fsync(fp.fileno())
            except OSError:
                pass
            fp.close()
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size <= 0:
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            self._enqueue(path, touch=True)

    def _finish_locked(self, reason: str) -> None:
        take = self._take
        if take is None:
            return
        self._close_parts_locked(take)
        ended = time.time()
        take.meta["recording"] = False
        take.meta["ended_at"] = _iso_now()
        take.meta["ended_unix"] = ended
        take.meta["duration_sec"] = max(0.0, ended - float(take.meta.get("started_unix") or ended))
        take.meta["stop_reason"] = reason
        take.meta["sample_count"] = take.samples
        take.meta["open_parts"] = []
        self._write_meta_locked(take)
        meta_path = take.directory / "meta.json"
        self._enqueue(meta_path, touch=True)
        rel = take.relative.as_posix()
        samples = take.samples
        self._take = None
        print(f"実験記録終了  {rel}  {samples}点")

    def _write_meta_locked(self, take: _Take) -> None:
        path = take.directory / "meta.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(take.meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)

    def _enqueue(self, src: Path, *, touch: bool) -> None:
        """印を付けてコピー待ちにする。archive 未設定なら何もしない。"""
        if self.paths is None or self.paths.archive_root is None:
            return
        marker = _pending_marker(src)
        if touch and not marker.exists():
            try:
                marker.write_text("", encoding="utf-8")
            except OSError:
                return
        if self._async:
            self._q.put(src)
        else:
            self._copy_one(src)

    def _copy_one(self, src: Path) -> bool:
        """閉じたファイルを archive_root の同じ相対パスへ。失敗しても記録は続けている。"""
        if self.paths is None or self.paths.archive_root is None:
            return False
        marker = _pending_marker(src)
        if not src.is_file():
            if marker.exists():
                try:
                    marker.unlink()
                except OSError:
                    pass
            return False
        try:
            rel = src.relative_to(self.paths.data_root)
        except ValueError:
            return False
        dest = self.paths.archive_root / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            if dest.stat().st_size != src.stat().st_size:
                raise OSError("size")
        except OSError:
            self._warn_copy(rel)
            return False
        if marker.exists():
            try:
                marker.unlink()
            except OSError:
                pass
        return True

    def _warn_copy(self, rel: Path) -> None:
        """保管先のパスは出さない。take 名だけ、60 秒に 1 回。"""
        parts = rel.parts
        label = parts[3] if len(parts) >= 4 else rel.as_posix()
        now = time.monotonic()
        with self._lock:
            last = self._warned_at.get(label, 0.0)
            if now - last < 60.0:
                return
            self._warned_at[label] = now
        print(f"保管先へまだ書けていません  {label}", file=sys.stderr)

    def _copy_loop(self) -> None:
        while True:
            try:
                src = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if src is None:
                return
            if not self._copy_one(src):
                # 印は残っている。NAS が戻ってから同じファイルを再送する。
                time.sleep(5.0)
                if src.is_file():
                    self._q.put(src)

    def _interrupted_metas(self, data_root: Path) -> list[Path]:
        found: list[Path] = []
        if not data_root.is_dir():
            return found
        for year in data_root.iterdir():
            if not year.is_dir() or not year.name.isdigit():
                continue
            for month in year.iterdir():
                if not month.is_dir() or not month.name.isdigit():
                    continue
                for day in month.iterdir():
                    if not day.is_dir() or not day.name.isdigit():
                        continue
                    for take in day.iterdir():
                        meta = take / "meta.json"
                        if meta.is_file():
                            found.append(meta)
        return found

    def _seal_interrupted(self, meta_path: Path) -> None:
        """プロセスが落ちた take を閉じ、残った断片をコピー待ちにする。"""
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(meta, dict) or not meta.get("recording"):
            return
        take_dir = meta_path.parent
        open_parts = meta.get("open_parts")
        if isinstance(open_parts, list):
            for rel in open_parts:
                if not isinstance(rel, str):
                    continue
                src = take_dir / rel
                if src.is_file() and src.stat().st_size > 0:
                    self._enqueue(src, touch=True)
        meta["recording"] = False
        meta["stop_reason"] = meta.get("stop_reason") or "中断"
        meta["ended_at"] = meta.get("ended_at") or _iso_now()
        meta["ended_unix"] = meta.get("ended_unix") or time.time()
        meta["open_parts"] = []
        tmp = meta_path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp.replace(meta_path)
        except OSError:
            return
        self._enqueue(meta_path, touch=True)


def shared() -> ExperimentLog:
    """最初の ver 15 HELLO で作る。設定の再読込はプロセス再起動。"""
    global _SHARED
    if _SHARED is None:
        _SHARED = ExperimentLog(load_storage())
        atexit.register(_SHARED.end_open, "プロセス終了")
    return _SHARED


def append_event(port: str, text: str) -> None:
    log = _SHARED
    if log is not None:
        log.append_event(port, text)


def append_frame(port: str, frame: dict[str, Any]) -> None:
    log = _SHARED
    if log is not None:
        log.append_frame(port, frame)


def append_command(port: str, command: dict[str, Any]) -> None:
    log = _SHARED
    if log is not None:
        log.append_command(port, command)


def end_if_started(port: str, reason: str) -> None:
    log = _SHARED
    if log is not None:
        log.end(port, reason)


def close_if_started(reason: str) -> None:
    log = _SHARED
    if log is not None:
        log.end_open(reason)
