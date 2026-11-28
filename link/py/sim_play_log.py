"""
Isaac Lab の再生が、方策の 1 周期をローカル SSD へ書く。

実機の core_take_v2 には混ぜない。フォルダは data_root/sim/年/月/日/連番_時分秒/。
開いている断片は NAS へ送らない。閉じた断片、schema.md、context.json だけを
archive_root の同じ相対パスへコピーする。失敗した分は印を残し、次の再生で再送する。

storage.yaml が無いときは、リポジトリの atom-rt/data/policy_traces/sim/ へ書く。
保管先の絶対パスはログに出さない。
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import experiment_log as _real
from policy_trace import read_next_name, repo_root
from take_context import action_rad, build_context

FORMAT_ID = "sim_play_v1"
SCHEMA_FILE = "schema.md"
CONTEXT_FILE = "context.json"
# 実機 take と連番を混ぜないための一段。data_root 直下の年フォルダには置かない。
SIM_DIR = "sim"
# 画面が渡す実験名。空のときは直立。
PLAY_TASK = "YuukiLab-BipedWalk-Play-v0"
# 実験中の正本は SSD。落ちて失うのは直前のこの秒数だけにする。
FLUSH_SEC = 1.5
# 閉じた断片を NAS へ出せる間隔。開いたままのファイルは対象にしない。
ROTATE_SEC = 60.0
# Hub の id。年月日_連番_時分秒。スラッシュは入れない。
_TAKE_ID = re.compile(r"^(\d{4})(\d{2})(\d{2})_(\d+_\d{6})$")

_SHARED: SimPlayLog | None = None


def schema_source() -> Path:
    """欄の説明の正本。take へは schema.md としてコピーする。"""
    return Path(__file__).resolve().parent.parent / "schema" / f"{FORMAT_ID}.md"


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _pending_marker(src: Path) -> Path:
    """閉じたファイルの隣に置く再送印。中身は空。"""
    return Path(str(src) + ".pending")


@dataclass
class _PlayTake:
    """実験名が同じあいだ開いている 1 本。"""

    directory: Path
    relative: Path
    meta: dict[str, Any]
    experiment: str
    part_index: int
    part_opened: float
    last_flush: float
    last_seq: int | None
    samples: int
    policy: Any
    policy_path: Path


class SimPlayLog:
    """再生プロセスに 1 つ。方策ステップは待たせず、NAS へのコピーは別スレッド。"""

    def __init__(
        self,
        paths: _real.StoragePaths | None,
        *,
        fallback_root: Path | None = None,
        flush_sec: float = FLUSH_SEC,
        rotate_sec: float = ROTATE_SEC,
        copy_async: bool = True,
        clock: Callable[[], float] | None = None,
        name_of: Callable[[], str] | None = None,
    ) -> None:
        self.paths = paths
        # storage.yaml が無いときだけ、リポジトリ内をローカルの根にする。
        self.local_root = paths.data_root if paths is not None else fallback_root
        self.archive_root = paths.archive_root if paths is not None else None
        self.flush_sec = flush_sec
        self.rotate_sec = rotate_sec
        self._clock = clock or time.monotonic
        self._name_of = name_of or read_next_name
        self._lock = threading.RLock()
        self._take: _PlayTake | None = None
        self._warned_at: dict[str, float] = {}
        self._q: queue.Queue[Path | None] = queue.Queue()
        self._async = bool(copy_async and self.archive_root is not None)
        self._thread: threading.Thread | None = None
        if self._async:
            self._thread = threading.Thread(
                target=self._copy_loop,
                name="sim-play-archive",
                daemon=True,
            )
            self._thread.start()
        self._catch_up()

    def write(self, row: dict[str, Any]) -> None:
        """方策 1 周期。実験名が変わると、それまでの take を閉じて新しい take を開く。

        action_rad は生出力に action_scale を掛けた、頭打ち前の直立からの目標。
        再生の cmd_rad は Isaac が関節へ渡した値で、実機の包絡は通っていない。
        """
        try:
            name = self._name_of()
        except OSError:
            name = "直立"
        with self._lock:
            if self.local_root is None:
                return
            if self._take is None or name != self._take.experiment:
                if self._take is not None:
                    self._finish_locked("実験名")
                self._begin_locked(name)
            take = self._take
            if take is None or take.policy is None:
                return
            seq = row.get("seq")
            if isinstance(seq, int) and seq == take.last_seq:
                return
            if isinstance(seq, int):
                take.last_seq = seq
            body = dict(row)
            body.setdefault("t", time.time())
            # 頭打ち前の目標。受信側が画面の度から作り直さないように、ここで足す。
            body["action_rad"] = action_rad(body.get("action"))
            self._write_line(take.policy, body)
            take.samples += 1
            take.meta["sample_count"] = take.samples
            self._after_write_locked(take)

    def close(self, reason: str = "再生終了") -> None:
        """開いている断片を閉じ、コピー待ちを 1 回だけ送る。NAS が無くても再生は終わる。"""
        pending: list[Path] = []
        with self._lock:
            self._finish_locked(reason)
            while True:
                try:
                    item = self._q.get_nowait()
                except queue.Empty:
                    break
                if item is not None:
                    pending.append(item)
        for src in pending:
            self._copy_one(src)

    def _begin_locked(self, name: str) -> None:
        if self.local_root is None:
            return
        now = datetime.now().astimezone()
        try:
            directory, day_index = self._allocate_dir(now)
            directory.mkdir(parents=True, exist_ok=False)
        except OSError:
            return
        relative = directory.relative_to(self.local_root)
        take_name = directory.name
        hub_id = f"{now:%Y%m%d}_{take_name}"
        meta: dict[str, Any] = {
            "format_id": FORMAT_ID,
            "id": hub_id,
            "name": name,
            "side": "sim",
            "take_id": take_name,
            "day_index": day_index,
            "started_at": now.isoformat(timespec="milliseconds"),
            "started_unix": time.time(),
            "ended_at": None,
            "ended_unix": None,
            "recording": True,
            "sample_count": 0,
            "stop_reason": "",
            "schema": "",
            "context": "",
            "task": PLAY_TASK,
            "open_parts": [],
        }
        take = _PlayTake(
            directory=directory,
            relative=relative,
            meta=meta,
            experiment=name,
            part_index=0,
            part_opened=self._clock(),
            last_flush=self._clock(),
            last_seq=None,
            samples=0,
            policy=None,
            policy_path=directory / "policy" / "part-000.jsonl",
        )
        self._take = take
        self._open_part_locked(take)
        if self._install_schema(take):
            self._enqueue(take.directory / SCHEMA_FILE)
        if self._install_context(take, name):
            self._enqueue(take.directory / CONTEXT_FILE)
        self._write_meta_locked(take)
        print(f"再生記録開始  {relative.as_posix()}")

    def _allocate_dir(self, now: datetime) -> tuple[Path, int]:
        """その日の次の連番。実機 take の日付フォルダとは sim/ で分ける。"""
        assert self.local_root is not None
        day = _real._day_dir(self.local_root / SIM_DIR, now)
        index = self._next_day_index(now)
        stamp = now.strftime("%H%M%S")
        directory = day / f"{index:03d}_{stamp}"
        while directory.exists():
            index += 1
            directory = day / f"{index:03d}_{stamp}"
        _real._write_last_index(day, index)
        if self.archive_root is not None:
            archive_day = _real._day_dir(self.archive_root / SIM_DIR, now)
            threading.Thread(
                target=_real._write_last_index,
                args=(archive_day, index),
                name="sim-play-day-index",
                daemon=True,
            ).start()
        return directory, index

    def _next_day_index(self, now: datetime) -> int:
        """ローカルと NAS の、その日の sim 連番の最大に 1 を足す。"""
        assert self.local_root is not None
        explicit, legacy = _real._peek_issued(_real._day_dir(self.local_root / SIM_DIR, now))
        archive_root = self.archive_root
        if archive_root is not None:
            found: list[tuple[int, int]] = []

            def _read_archive() -> None:
                found.append(_real._peek_issued(_real._day_dir(archive_root / SIM_DIR, now)))

            worker = threading.Thread(target=_read_archive, name="sim-play-day-index-read", daemon=True)
            worker.start()
            worker.join(_real._ARCHIVE_INDEX_TIMEOUT_SEC)
            if found:
                explicit = max(explicit, found[0][0])
                legacy = max(legacy, found[0][1])
        return max(explicit, legacy) + 1

    def _open_part_locked(self, take: _PlayTake) -> None:
        idx = f"{take.part_index:03d}"
        take.policy_path = take.directory / "policy" / f"part-{idx}.jsonl"
        take.policy_path.parent.mkdir(parents=True, exist_ok=True)
        # 行バッファにしない。FLUSH_SEC までメモリに溜める。
        take.policy = take.policy_path.open("a", encoding="utf-8", buffering=64 * 1024)
        take.part_opened = self._clock()
        take.meta["open_parts"] = [take.policy_path.relative_to(take.directory).as_posix()]

    def _write_line(self, fp: Any, obj: dict[str, Any]) -> None:
        fp.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")

    def _after_write_locked(self, take: _PlayTake) -> None:
        now = self._clock()
        if now - take.last_flush >= self.flush_sec:
            self._flush_locked(take)
            take.last_flush = now
        if now - take.part_opened >= self.rotate_sec:
            self._rotate_locked(take)

    def _flush_locked(self, take: _PlayTake) -> None:
        if take.policy is None:
            return
        take.policy.flush()
        try:
            os.fsync(take.policy.fileno())
        except OSError:
            pass
        self._write_meta_locked(take)

    def _rotate_locked(self, take: _PlayTake) -> None:
        """約 60 秒で断片を閉じる。閉じたものだけがコピー待ちになる。"""
        self._close_part_locked(take)
        take.part_index += 1
        self._open_part_locked(take)
        self._write_meta_locked(take)

    def _close_part_locked(self, take: _PlayTake) -> None:
        fp = take.policy
        path = take.policy_path
        take.policy = None
        if fp is None:
            return
        try:
            fp.flush()
            os.fsync(fp.fileno())
        except OSError:
            pass
        fp.close()
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size <= 0:
            try:
                path.unlink()
            except OSError:
                pass
            return
        self._enqueue(path)

    def _finish_locked(self, reason: str) -> None:
        take = self._take
        if take is None:
            return
        self._close_part_locked(take)
        ended = time.time()
        take.meta["recording"] = False
        take.meta["ended_at"] = _iso_now()
        take.meta["ended_unix"] = ended
        take.meta["duration_sec"] = max(0.0, ended - float(take.meta.get("started_unix") or ended))
        take.meta["stop_reason"] = reason
        take.meta["sample_count"] = take.samples
        take.meta["open_parts"] = []
        self._write_meta_locked(take)
        self._enqueue(take.directory / "meta.json")
        rel = take.relative.as_posix()
        samples = take.samples
        self._take = None
        print(f"再生記録終了  {rel}  {samples}行")

    def _write_meta_locked(self, take: _PlayTake) -> None:
        path = take.directory / "meta.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(take.meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _install_schema(self, take: _PlayTake) -> bool:
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

    def _install_context(self, take: _PlayTake, experiment: str) -> bool:
        """別システムが、このフォルダだけで目標角の意味を読めるようにする。"""
        dest = take.directory / CONTEXT_FILE
        try:
            text = json.dumps(build_sim_context(experiment), ensure_ascii=False, indent=2) + "\n"
            dest.write_text(text, encoding="utf-8")
        except (OSError, TypeError, ValueError):
            return False
        take.meta["context"] = CONTEXT_FILE
        return True

    def _enqueue(self, src: Path) -> None:
        """印を付けてコピー待ちにする。archive が無いときは何もしない。"""
        if self.archive_root is None or self.local_root is None:
            return
        marker = _pending_marker(src)
        if not marker.exists():
            try:
                marker.write_text("", encoding="utf-8")
            except OSError:
                return
        if self._async:
            self._q.put(src)
        else:
            self._copy_one(src)

    def _copy_one(self, src: Path) -> bool:
        """閉じたファイルを archive_root の同じ相対パスへ。失敗しても再生は続ける。"""
        if self.archive_root is None or self.local_root is None:
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
            rel = src.relative_to(self.local_root)
        except ValueError:
            return False
        dest = self.archive_root / rel
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
        label = parts[4] if len(parts) >= 5 else rel.as_posix()
        now = time.monotonic()
        with self._lock:
            last = self._warned_at.get(label, 0.0)
            if now - last < 60.0:
                return
            self._warned_at[label] = now
        print(f"再生の保管先へまだ書けていません  {label}", file=sys.stderr)

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

    def _catch_up(self) -> None:
        """落ちた再生の断片と、送れなかった印を、次の起動で閉じる。実機の年フォルダは見ない。"""
        if self.local_root is None:
            return
        sim_root = self.local_root / SIM_DIR
        if not sim_root.is_dir():
            return
        for meta_path in _sim_metas(sim_root):
            self._seal_interrupted(meta_path)
        if self.archive_root is None:
            return
        seen: set[Path] = set()
        for marker in sim_root.rglob("*.pending"):
            if not marker.is_file() or not marker.name.endswith(".pending"):
                continue
            src = Path(str(marker)[: -len(".pending")])
            if src in seen or not src.is_file():
                continue
            seen.add(src)
            self._enqueue(src)

    def _seal_interrupted(self, meta_path: Path) -> None:
        """プロセスが落ちた take を閉じ、残った断片をコピー待ちにする。"""
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(meta, dict) or meta.get("format_id") != FORMAT_ID or not meta.get("recording"):
            return
        take_dir = meta_path.parent
        open_parts = meta.get("open_parts")
        if isinstance(open_parts, list):
            for rel in open_parts:
                if not isinstance(rel, str):
                    continue
                src = take_dir / rel
                if src.is_file() and src.stat().st_size > 0:
                    self._enqueue(src)
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
        self._enqueue(meta_path)


def build_sim_context(experiment: str) -> dict[str, Any]:
    """再生 take を開いた瞬間に書く契約。実機の包絡はこの目標に掛かっていない。"""
    base = build_context()
    project = dict(base.get("project") or {})
    policy = dict(base.get("policy") or {})
    policy["action_rad"] = (
        "action に action_scale を掛けた、直立からの目標 [rad]。頭打ちの前。"
        "再生はこの値をサーボの速度制限にも、前進 0 の包絡にも通さない。"
    )
    policy["cmd_rad"] = (
        "Isaac Lab が関節へ渡した目標。直立 0 rad に action * action_scale を足した値。"
        "方策の関節順。再生では action_rad とほぼ同じで、実機の包絡は通っていない。"
    )
    policy["envelope"] = "この再生には、実機の前進 0 の包絡は無い。ネットが欲しかった角度は action_rad。"
    return {
        "format_id": FORMAT_ID,
        "schema": SCHEMA_FILE,
        "side": "sim",
        "experiment": experiment,
        "project": {
            "name": project.get("name") or "yuuki-lab",
            "task": PLAY_TASK,
            "robot": project.get("robot") or "",
            "learn_run": project.get("learn_run") or "",
            "checkpoint": project.get("checkpoint") or "",
            "weights": project.get("weights") or "",
        },
        "time": {
            "clock": "policy の t は、再生を動かしている PC の UNIX 秒。実機 take の t とは合わせない。",
            "align": "実機とは実験名で分布を比べる。同じ秒数の行は比べない。",
        },
        "body_frame": base.get("body_frame") or {},
        "policy_joints": base.get("policy_joints") or [],
        "policy": policy,
    }


def sim_roots() -> list[Path]:
    """Hub が読むローカルの sim 根。NAS は含めない。"""
    roots: list[Path] = []
    storage = _real.load_storage()
    if storage is not None:
        roots.append(storage.data_root / SIM_DIR)
    roots.append(repo_root() / "atom-rt" / "data" / "policy_traces" / SIM_DIR)
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def list_play_takes(roots: list[Path] | None = None) -> list[dict[str, Any]]:
    """閉じた再生と、いま書いている再生。行が 1 つも無い take は出さない。"""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in sim_roots() if roots is None else roots:
        for meta_path in _sim_metas(root):
            row = _list_row(meta_path)
            if row is None or row["id"] in seen:
                continue
            seen.add(row["id"])
            found.append(row)
    return found


def find_play_take(rec_id: str, roots: list[Path] | None = None) -> Path | None:
    """Hub の id から、ローカルの take フォルダを返す。保管先は見ない。"""
    match = _TAKE_ID.match(rec_id or "")
    if match is None:
        return None
    year, month, day, folder = match.groups()
    for root in sim_roots() if roots is None else roots:
        take = root / year / month / day / folder
        meta = take / "meta.json"
        if not meta.is_file():
            continue
        try:
            body = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(body, dict) and body.get("format_id") == FORMAT_ID:
            return take
    return None


def _sim_metas(sim_root: Path) -> list[Path]:
    """sim/年/月/日/take/meta.json。実機の日付フォルダは sim の外なので来ない。"""
    found: list[Path] = []
    if not sim_root.is_dir():
        return found
    for year in sim_root.iterdir():
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


def _list_row(meta_path: Path) -> dict[str, Any] | None:
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict) or meta.get("format_id") != FORMAT_ID:
        return None
    count = int(meta.get("sample_count") or 0)
    if count <= 0:
        count = _count_parts(meta_path.parent)
    if count <= 0:
        return None
    take = meta_path.parent
    return {
        "id": str(meta.get("id") or take.name),
        "name": str(meta.get("name") or ""),
        "side": "sim",
        "sample_count": count,
        "started_at": meta.get("started_at") or "",
    }


def _count_parts(take: Path) -> int:
    policy = take / "policy"
    if not policy.is_dir():
        return 0
    total = 0
    for part in sorted(policy.glob("part-*.jsonl")):
        try:
            with part.open("r", encoding="utf-8") as handle:
                total += sum(1 for line in handle if line.strip())
        except OSError:
            continue
    return total


def shared_sim_log() -> SimPlayLog:
    """再生プロセスの中で 1 つ。設定の再読込はプロセス再起動。"""
    global _SHARED
    if _SHARED is None:
        fallback = repo_root() / "atom-rt" / "data" / "policy_traces"
        _SHARED = SimPlayLog(_real.load_storage(), fallback_root=fallback)
        atexit.register(_SHARED.close, "プロセス終了")
    return _SHARED
