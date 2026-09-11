#!/usr/bin/env python3
"""
ATOM / M5 テレメトリの本記録ストア。

明示開始〜停止のあいだだけ、ATOM 接続 PC のディスクへ書く。
robotics-hub は HTTP API（m5_hub_bridge）経由で一覧・配信・メタ編集する。
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


FORMAT_ID = "m5_take_v1"
# 1 回の frames API で返す上限（Hub はチャンクで足す）
MAX_FRAME_CHUNK = 8000


def default_recordings_root() -> Path:
    """atom-rt/data/recordings。無ければ作る。"""
    return Path(__file__).resolve().parent.parent / "data" / "recordings"


def iso_now() -> str:
    """ローカルタイムゾーン付き ISO 8601（ミリ秒）。"""
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _new_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{secrets.token_hex(2)}"


def _safe_meta(raw: dict[str, Any]) -> dict[str, Any]:
    """欠損があっても Hub が落ちないよう、一覧用の最低限を埋める。"""
    started_unix = float(raw.get("started_unix") or 0.0)
    ended_unix = raw.get("ended_unix")
    duration = raw.get("duration_sec")
    if duration is None and isinstance(ended_unix, (int, float)) and started_unix:
        duration = max(0.0, float(ended_unix) - started_unix)
    return {
        "format_id": raw.get("format_id") or FORMAT_ID,
        "id": str(raw.get("id") or ""),
        "name": str(raw.get("name") or ""),
        "notes": str(raw.get("notes") or ""),
        "started_at": raw.get("started_at") or "",
        "ended_at": raw.get("ended_at"),
        "started_unix": started_unix,
        "ended_unix": ended_unix,
        "duration_sec": duration,
        "sample_count": int(raw.get("sample_count") or 0),
        "hz": int(raw.get("hz") or 20),
        "port": str(raw.get("port") or ""),
        "atom_name": str(raw.get("atom_name") or ""),
        "mode": str(raw.get("mode") or ""),
        "hello": str(raw.get("hello") or ""),
        "recording": bool(raw.get("recording")),
        "bytes": int(raw.get("bytes") or 0),
    }


class M5RecordStore:
    """
    1 プロセスにつき 1 つ。記録中は frames.jsonl を開きっぱなし。
    Tk スレッドが start/append/stop、Flask スレッドが list/read/patch/delete。
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_recordings_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._id: str | None = None
        self._meta: dict[str, Any] | None = None
        self._fp: Any = None
        self._last_seq: int | None = None
        self._last_pub = 0.0

    def is_recording(self) -> bool:
        with self._lock:
            return self._fp is not None

    def status(self) -> dict[str, Any]:
        """Socket.IO / ヘルス用の短い状態。"""
        with self._lock:
            if self._meta is None or self._fp is None:
                return {
                    "recording": False,
                    "id": None,
                    "name": "",
                    "notes": "",
                    "started_at": None,
                    "sample_count": 0,
                    "elapsed_sec": 0.0,
                }
            started = float(self._meta.get("started_unix") or time.time())
            return {
                "recording": True,
                "id": self._meta.get("id"),
                "name": self._meta.get("name") or "",
                "notes": self._meta.get("notes") or "",
                "started_at": self._meta.get("started_at"),
                "sample_count": int(self._meta.get("sample_count") or 0),
                "elapsed_sec": max(0.0, time.time() - started),
            }

    def start(
        self,
        *,
        name: str = "",
        notes: str = "",
        port: str = "",
        atom_name: str = "",
        mode: str = "",
        hello: str = "",
        profile: dict[str, Any] | None = None,
        scan: dict[str, Any] | None = None,
        control: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """本記録を開始する。すでに記録中ならその状態を返す。"""
        with self._lock:
            if self._fp is not None and self._meta is not None:
                out = dict(self._meta)
                out["ok"] = True
                out["already"] = True
                return out
            rec_id = _new_id()
            folder = self.root / rec_id
            folder.mkdir(parents=True, exist_ok=False)
            started_unix = time.time()
            label = (name or "").strip() or f"{atom_name or port or 'ATOM'} {datetime.now():%Y-%m-%d %H:%M}"
            meta: dict[str, Any] = {
                "format_id": FORMAT_ID,
                "id": rec_id,
                "name": label,
                "notes": (notes or "").strip(),
                "started_at": iso_now(),
                "ended_at": None,
                "started_unix": started_unix,
                "ended_unix": None,
                "duration_sec": None,
                "sample_count": 0,
                "hz": 20,
                "port": port,
                "atom_name": atom_name,
                "mode": mode,
                "hello": hello,
                "recording": True,
            }
            (folder / "profile.json").write_text(
                json.dumps(profile or {}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (folder / "scan.json").write_text(
                json.dumps(scan or {}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (folder / "control.json").write_text(
                json.dumps(control or {}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._write_meta_unlocked(folder, meta)
            self._fp = (folder / "frames.jsonl").open("a", encoding="utf-8")
            self._id = rec_id
            self._meta = meta
            self._last_seq = None
            out = dict(meta)
            out["ok"] = True
            return out

    def append(self, frame: dict[str, Any]) -> bool:
        """1 サンプルを追記。同じ seq は捨てる。"""
        with self._lock:
            if self._fp is None or self._meta is None:
                return False
            seq = frame.get("seq")
            if isinstance(seq, int) and seq == self._last_seq:
                return False
            if isinstance(seq, int):
                self._last_seq = seq
            self._fp.write(json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n")
            self._meta["sample_count"] = int(self._meta.get("sample_count") or 0) + 1
            # 20 Hz なので 1 秒に 1 回フラッシュ
            if int(self._meta["sample_count"]) % 20 == 0:
                self._fp.flush()
            return True

    def stop(self, reason: str = "") -> dict[str, Any]:
        """記録を閉じ、終了時刻と点数を確定する。"""
        with self._lock:
            if self._fp is None or self._meta is None:
                return {"ok": True, "recording": False, "id": None}
            try:
                self._fp.flush()
            finally:
                self._fp.close()
                self._fp = None
            ended_unix = time.time()
            self._meta["recording"] = False
            self._meta["ended_at"] = iso_now()
            self._meta["ended_unix"] = ended_unix
            self._meta["duration_sec"] = max(
                0.0, ended_unix - float(self._meta.get("started_unix") or ended_unix)
            )
            if reason:
                self._meta["stop_reason"] = reason
            folder = self.root / str(self._meta["id"])
            frames_path = folder / "frames.jsonl"
            if frames_path.is_file():
                self._meta["bytes"] = frames_path.stat().st_size
            self._write_meta_unlocked(folder, self._meta)
            out = dict(self._meta)
            out["ok"] = True
            self._id = None
            self._meta = None
            self._last_seq = None
            return out

    def list_recordings(self) -> list[dict[str, Any]]:
        """新しい順。記録中のものも含む。"""
        items: list[dict[str, Any]] = []
        with self._lock:
            live_id = self._id
            live_meta = dict(self._meta) if self._meta else None
            if live_meta is not None:
                live_meta["duration_sec"] = max(
                    0.0, time.time() - float(live_meta.get("started_unix") or time.time())
                )
        for folder in self.root.iterdir() if self.root.is_dir() else []:
            if not folder.is_dir():
                continue
            meta_path = folder / "meta.json"
            if not meta_path.is_file():
                continue
            rec_id = folder.name
            if live_id and rec_id == live_id and live_meta is not None:
                row = _safe_meta(live_meta)
            else:
                try:
                    raw = json.loads(meta_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                row = _safe_meta(raw if isinstance(raw, dict) else {})
            if not row["id"]:
                row["id"] = rec_id
            frames_path = folder / "frames.jsonl"
            if frames_path.is_file() and not row.get("bytes"):
                try:
                    row["bytes"] = frames_path.stat().st_size
                except OSError:
                    row["bytes"] = 0
            items.append(row)
        items.sort(key=lambda x: float(x.get("started_unix") or 0.0), reverse=True)
        return items

    def get_recording(self, rec_id: str) -> dict[str, Any] | None:
        """メタ + 開始時スナップショット。フレームは含めない。"""
        folder = self._folder(rec_id)
        if folder is None:
            return None
        with self._lock:
            if self._id == rec_id and self._meta is not None:
                meta = _safe_meta(self._meta)
                meta["duration_sec"] = max(
                    0.0, time.time() - float(self._meta.get("started_unix") or time.time())
                )
            else:
                try:
                    raw = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    return None
                if not isinstance(raw, dict):
                    return None
                meta = _safe_meta(raw)
        if not meta["id"]:
            meta["id"] = rec_id
        meta["profile"] = self._read_json(folder / "profile.json")
        meta["scan"] = self._read_json(folder / "scan.json")
        meta["control"] = self._read_json(folder / "control.json")
        return meta

    def read_frames(self, rec_id: str, offset: int = 0, limit: int = 4000) -> tuple[list[dict[str, Any]], int]:
        """jsonl を offset から limit 件。total は行数（記録中は概算）。"""
        folder = self._folder(rec_id)
        if folder is None:
            return [], 0
        path = folder / "frames.jsonl"
        if not path.is_file():
            return [], 0
        offset = max(0, int(offset))
        limit = max(1, min(int(limit), MAX_FRAME_CHUNK))
        frames: list[dict[str, Any]] = []
        total = 0
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                if offset <= total < offset + limit:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        total += 1
                        continue
                    if isinstance(obj, dict):
                        frames.append(obj)
                total += 1
                # 読み終わったあと残り行も数える
                if total >= offset + limit:
                    for rest in fp:
                        if rest.strip():
                            total += 1
                    break
        with self._lock:
            if self._id == rec_id and self._meta is not None:
                total = max(total, int(self._meta.get("sample_count") or total))
        return frames, total

    def patch(self, rec_id: str, *, name: str | None = None, notes: str | None = None) -> dict[str, Any] | None:
        """データ名と実験メモだけ後から直す。"""
        folder = self._folder(rec_id)
        if folder is None:
            return None
        with self._lock:
            if self._id == rec_id and self._meta is not None:
                if name is not None:
                    self._meta["name"] = name.strip() or self._meta.get("name") or rec_id
                if notes is not None:
                    self._meta["notes"] = notes
                self._write_meta_unlocked(folder, self._meta)
                return _safe_meta(self._meta)
        try:
            raw = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        if name is not None:
            raw["name"] = name.strip() or raw.get("name") or rec_id
        if notes is not None:
            raw["notes"] = notes
        self._write_meta_unlocked(folder, raw)
        return _safe_meta(raw)

    def delete(self, rec_id: str) -> tuple[bool, str]:
        """記録中は消さない。フォルダごと削除。"""
        with self._lock:
            if self._id == rec_id:
                return False, "記録中は削除できません"
        folder = self._folder(rec_id)
        if folder is None:
            return False, "見つかりません"
        import shutil

        try:
            shutil.rmtree(folder)
        except OSError as exc:
            return False, str(exc)
        return True, ""

    def _folder(self, rec_id: str) -> Path | None:
        if not rec_id or "/" in rec_id or "\\" in rec_id or rec_id in (".", ".."):
            return None
        folder = self.root / rec_id
        if not folder.is_dir() or not (folder / "meta.json").is_file():
            return None
        return folder

    def _write_meta_unlocked(self, folder: Path, meta: dict[str, Any]) -> None:
        tmp = folder / "meta.json.tmp"
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(folder / "meta.json")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}
