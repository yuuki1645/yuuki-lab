# -*- coding: utf-8 -*-
"""Read core_take_v1 and core_take_v2 folders. The NAS files stay the record.

Layout (see schema.md inside each take):

    2026/10/26/004_120252/meta.json
    2026/10/26/004_120252/sensors/part-000.jsonl
    2026/10/26/004_120252/events/part-000.log

part-NNN files are one timeline in numeric order. A null sensor value is a
gap, not 0 degrees or 0 amps. Foot force is also a gap when that foot's ok
flag is false, even if the file stored 0 kg.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from take_view.config import lab_experiments_root
from take_view.schemas import (
    LabDay,
    LabDaysResponse,
    LabEvent,
    LabEventsResponse,
    LabFootSummary,
    LabJointSummary,
    LabSeriesPoint,
    LabSeriesResponse,
    LabTakeDetail,
    LabTakeMeta,
    LabTakesResponse,
)

# v2 adds policy/ and context.json. Sensor rows stay readable by the v1 parser.
# sim_play_v1 is an Isaac Lab playback. It lives under sim/ and has no sensor file.
SUPPORTED_FORMATS = frozenset({"core_take_v1", "core_take_v2", "sim_play_v1"})
FORMAT_ID = "core_take_v1"
JOINT_COUNT = 10

# Logical axis order from schema.md. Index is the array slot and the CMD channel.
JOINT_NAMES: tuple[str, ...] = (
    "\u53f3\u80a1\u30ed\u30fc\u30eb",
    "\u53f3\u80a1\u30d4\u30c3\u30c1",
    "\u53f3\u3072\u3056",
    "\u53f3\u304b\u304b\u3068\u30d4\u30c3\u30c1",
    "\u53f3\u304b\u304b\u3068\u30ed\u30fc\u30eb",
    "\u5de6\u80a1\u30ed\u30fc\u30eb",
    "\u5de6\u80a1\u30d4\u30c3\u30c1",
    "\u5de6\u3072\u3056",
    "\u5de6\u304b\u304b\u3068\u30d4\u30c3\u30c1",
    "\u5de6\u304b\u304b\u3068\u30ed\u30fc\u30eb",
)

# Per-sample arrays indexed by joint. Global fields do not need a joint.
PER_JOINT_FIELDS = frozenset({"cmd", "corr", "raw", "unwrap", "amp", "watt", "volt"})
GLOBAL_FIELDS = frozenset({"foot_force_kg", "foot_left_force_kg"})
SERIES_FIELDS = PER_JOINT_FIELDS | GLOBAL_FIELDS

_DAY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
# 004_120252 after numbering, or 095959 from before numbering started.
_TAKE_RE = re.compile(r"^(?:\d{3}_\d{6}|\d{6})$")
_PART_RE = re.compile(r"part-(\d+)")
_EVENT_RE = re.compile(r"^(\S+)\s{2,}(.*)$")

# User-facing errors. Kept here so routers stay thin.
ERR_NOT_FOUND = "\u3053\u306e\u5b9f\u9a13\u306f\u898b\u3064\u304b\u308a\u307e\u305b\u3093"
ERR_BAD_ID = "\u65e5\u4ed8\u307e\u305f\u306f take \u306e\u6307\u5b9a\u304c\u9055\u3044\u307e\u3059"
ERR_BAD_FIELD = "\u4f7f\u3048\u306a\u3044\u9805\u76ee\u304c\u542b\u307e\u308c\u3066\u3044\u307e\u3059"
ERR_NEED_JOINT = "\u95a2\u7bc0\u306e\u9805\u76ee\u306b\u306f joint \u304c\u5fc5\u8981\u3067\u3059"
ERR_BAD_JOINT = "joint \u306f 0 \u304b\u3089 9 \u3067\u3059"
ERR_UNSUPPORTED = "\u3053\u306e\u5f62\u5f0f\u306f\u307e\u3060\u958b\u3051\u307e\u305b\u3093"
ERR_AMBIGUOUS = "\u540c\u3058\u540d\u524d\u306e take \u304c\u5b9f\u6a5f\u3068\u30b7\u30df\u30e5\u306e\u4e21\u65b9\u306b\u3042\u308a\u307e\u3059"


class LabError(Exception):
    """Expected failure with an HTTP status. message is safe to show."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def list_days() -> LabDaysResponse:
    """Newest day first. .last_index and non-take files are ignored."""
    root = _root()
    if not root.is_dir():
        return LabDaysResponse(root=str(root), available=False, days=[])

    # Real takes sit at root/YYYY/MM/DD. Playbacks sit at root/sim/YYYY/MM/DD
    # and share the calendar day, so one tab lists both.
    counts: dict[str, int] = {}
    for base in _storage_roots(root):
        for day, folder in _iter_day_dirs(base):
            count = sum(1 for _ in _iter_take_dirs(folder))
            if count:
                counts[day] = counts.get(day, 0) + count
    days = [LabDay(day=day, take_count=count) for day, count in counts.items()]
    days.sort(key=lambda item: item.day, reverse=True)
    return LabDaysResponse(root=str(root), available=True, days=days)


def list_takes(day: str) -> LabTakesResponse:
    """One calendar day, real takes and playbacks together.

    A real take is described from meta.json. A playback that has not written
    meta.json yet is described from context.json plus the policy parts.
    """
    folders = _day_dirs(day)
    if not folders:
        raise LabError(404, ERR_NOT_FOUND)
    takes: list[LabTakeMeta] = []
    for folder in folders:
        for path in _iter_take_dirs(folder):
            takes.append(_load_meta(day, path))
    takes.sort(key=lambda item: (item.started_unix is not None, item.started_unix or 0.0), reverse=True)
    return LabTakesResponse(day=day, takes=takes)


def get_take(day: str, take_id: str, side: str | None = None) -> LabTakeDetail:
    """meta plus a health pass. Unknown formats return meta and skip sensors."""
    take_dir = _take_dir(day, take_id, side)
    meta = _load_meta(day, take_dir)
    tail_pending = bool(meta.recording or meta.open_parts)
    if not meta.supported:
        return LabTakeDetail(meta=meta, tail_pending=tail_pending)

    summary = _summarize(take_dir)
    return LabTakeDetail(meta=meta, tail_pending=tail_pending, **summary)


def get_series(
    day: str,
    take_id: str,
    *,
    fields: list[str],
    joint: int | None,
    max_points: int,
    side: str | None = None,
) -> LabSeriesResponse:
    """Downsampled chart points. Buckets that are entirely missing stay null."""
    requested = _clean_fields(fields)
    if any(name in PER_JOINT_FIELDS for name in requested) and joint is None:
        raise LabError(400, ERR_NEED_JOINT)
    if joint is not None and not 0 <= joint < JOINT_COUNT:
        raise LabError(400, ERR_BAD_JOINT)

    take_dir = _take_dir(day, take_id, side)
    meta = _load_meta(day, take_dir)
    if not meta.supported:
        raise LabError(422, ERR_UNSUPPORTED)

    rows = [
        _project_row(sample, requested, joint)
        for sample in _iter_sensor_rows(take_dir)
        if isinstance(sample.get("t"), (int, float)) and not isinstance(sample.get("t"), bool)
    ]
    reduced, downsampled = _downsample(rows, max_points)
    origin = reduced[0]["t"] if reduced else 0.0
    points = [
        LabSeriesPoint(
            t=float(row["t"]),
            t_offset_sec=float(row["t"]) - float(origin),
            values={name: _as_float_or_none(row.get(name)) for name in requested},
        )
        for row in reduced
    ]
    return LabSeriesResponse(
        day=day,
        take_id=take_id,
        joint=joint,
        joint_name=JOINT_NAMES[joint] if joint is not None else None,
        fields=requested,
        sample_count=len(rows),
        point_count=len(points),
        downsampled=downsampled,
        points=points,
    )


def get_events(day: str, take_id: str, *, limit: int, side: str | None = None) -> LabEventsResponse:
    """Screen log lines. These are text, not sensor samples."""
    take_dir = _take_dir(day, take_id, side)
    meta = _load_meta(day, take_dir)
    if not meta.supported:
        raise LabError(422, ERR_UNSUPPORTED)

    started = parse_iso(meta.started_at) if meta.started_at else None
    events: list[LabEvent] = []
    for line in iter_event_lines(take_dir):
        stamp, text = split_event(line)
        offset = None
        parsed = parse_iso(stamp) if stamp else None
        if started is not None and parsed is not None:
            offset = (parsed - started).total_seconds()
        events.append(LabEvent(t_iso=stamp, t_offset_sec=offset, text=text))

    total = len(events)
    truncated = total > limit
    return LabEventsResponse(
        day=day,
        take_id=take_id,
        total=total,
        truncated=truncated,
        events=events[:limit],
    )


def resolve_supported_take(day: str, take_id: str, side: str | None = None) -> tuple[Path, LabTakeMeta]:
    """Validated take folder plus meta. 422 when the format is not supported.

    The analysis module uses this so path checks live in one place.
    ``side`` is "robot" or "sim" when the same folder name exists in both trees.
    """
    take_dir = _take_dir(day, take_id, side)
    meta = _load_meta(day, take_dir)
    if not meta.supported:
        raise LabError(422, ERR_UNSUPPORTED)
    return take_dir, meta


def _root() -> Path:
    return lab_experiments_root().resolve()


def _iter_day_dirs(root: Path) -> Iterator[tuple[str, Path]]:
    for year in root.iterdir():
        if not year.is_dir() or not _digits(year.name, 4):
            continue
        for month in year.iterdir():
            if not month.is_dir() or not month.name.isdigit():
                continue
            for day in month.iterdir():
                if not day.is_dir() or not day.name.isdigit():
                    continue
                label = f"{year.name}-{int(month.name):02d}-{int(day.name):02d}"
                yield label, day


def _iter_take_dirs(day_dir: Path) -> Iterator[Path]:
    for child in day_dir.iterdir():
        if _is_take(child):
            yield child


def _is_take(path: Path) -> bool:
    """A take folder. Playbacks may have context.json and policy/ before meta.json exists."""
    if not path.is_dir() or not _TAKE_RE.match(path.name):
        return False
    if (path / "meta.json").is_file():
        return True
    return (path / "context.json").is_file() and (path / "policy").is_dir()


def _storage_roots(root: Path) -> list[Path]:
    """Lab root, plus root/sim when that archive is present."""
    roots = [root]
    sim = root / "sim"
    if sim.is_dir():
        roots.append(sim)
    return roots


def _day_dirs(day: str) -> list[Path]:
    """Existing day folders, real first and then the sim archive."""
    match = _DAY_RE.match(day)
    if not match:
        raise LabError(400, ERR_BAD_ID)
    root = _root()
    found: list[Path] = []
    for base in _storage_roots(root):
        folder = (base / match.group(1) / match.group(2) / match.group(3)).resolve()
        _jail(root, folder)
        if folder.is_dir():
            found.append(folder)
    return found


def _side_of(take_dir: Path) -> str:
    """"sim" when the take sits under the sim archive, else "robot".

    root/sim/YYYY/MM/DD/take -> parents[3] is sim.
    root/YYYY/MM/DD/take -> parents[3] is the lab root.
    """
    try:
        return "sim" if take_dir.parents[3].name == "sim" else "robot"
    except IndexError:
        return "robot"


def _day_dir(day: str) -> Path:
    match = _DAY_RE.match(day)
    if not match:
        raise LabError(400, ERR_BAD_ID)
    root = _root()
    folder = (root / match.group(1) / match.group(2) / match.group(3)).resolve()
    _jail(root, folder)
    return folder


def _take_dir(day: str, take_id: str, side: str | None = None) -> Path:
    """Resolve one take. Search the real day, then the sim day.

    ``side`` picks one tree when the same folder name exists in both.
    Serial numbers are counted separately, so that collision is possible.
    """
    if not _TAKE_RE.match(take_id):
        raise LabError(400, ERR_BAD_ID)
    if side not in (None, "", "robot", "sim"):
        raise LabError(400, ERR_BAD_ID)
    root = _root()
    matches: list[Path] = []
    for folder in _day_dirs(day):
        path = (folder / take_id).resolve()
        _jail(root, path)
        if _is_take(path):
            matches.append(path)
    if side in ("robot", "sim"):
        matches = [path for path in matches if _side_of(path) == side]
    if not matches:
        raise LabError(404, ERR_NOT_FOUND)
    if len(matches) > 1:
        raise LabError(409, ERR_AMBIGUOUS)
    return matches[0]


def _jail(root: Path, path: Path) -> None:
    """Reject a resolved path that climbed out of the experiment root."""
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise LabError(400, ERR_BAD_ID) from exc


def _load_meta(day: str, take_dir: Path) -> LabTakeMeta:
    """meta.json when the writer made one, otherwise a playback synthesized from context."""
    side = _side_of(take_dir)
    path = take_dir / "meta.json"
    if path.is_file():
        meta = _meta_from_file(day, path, take_dir.name)
        if meta.take_id != take_dir.name:
            # Trust the folder name. A mismatched meta id must not retarget reads.
            meta.take_id = take_dir.name
        # The directory decides robot vs sim. A playback copied under sim/ stays sim.
        meta.side = side
        if not meta.name:
            meta.name = _experiment_of(take_dir)
        if side == "sim" and not meta.notes and meta.name:
            meta.notes = meta.name
        return meta
    return _meta_from_playback(day, take_dir, side)


def _meta_from_file(day: str, path: Path, folder_name: str) -> LabTakeMeta:
    raw = _read_json_object(path)
    format_id = _text(raw.get("format_id"))
    open_parts = raw.get("open_parts")
    parts = [str(item) for item in open_parts] if isinstance(open_parts, list) else []
    return LabTakeMeta(
        day=day,
        take_id=folder_name,
        format_id=format_id,
        side=_side_text(raw.get("side")),
        name=_text(raw.get("name")),
        day_index=_int_or_none(raw.get("day_index")),
        started_at=_text(raw.get("started_at")),
        ended_at=_text(raw.get("ended_at")),
        started_unix=_float_or_none(raw.get("started_unix")),
        ended_unix=_float_or_none(raw.get("ended_unix")),
        recording=bool(raw.get("recording")),
        notes=_text(raw.get("notes")) or "",
        hello=_text(raw.get("hello")),
        port=_text(raw.get("port")),
        fw_ver=_int_or_none(raw.get("fw_ver")),
        sample_count=_int_or_none(raw.get("sample_count")),
        policy_count=_int_or_none(raw.get("policy_count")),
        stop_reason=_text(raw.get("stop_reason")),
        duration_sec=_float_or_none(raw.get("duration_sec")),
        open_parts=parts,
        supported=format_id in SUPPORTED_FORMATS,
    )


def _meta_from_playback(day: str, take_dir: Path, side: str) -> LabTakeMeta:
    """A sim_play_v1 folder that has context.json and policy/ but no meta.json yet.

    The list still needs a start time and a length. Those come from the first
    policy row: wall-clock ``t`` is when the playback ran, and ``t_period_us``
    times the row count is how long the simulation itself lasted.
    """
    raw = _read_json_optional(take_dir / "context.json") or {}
    format_id = _text(raw.get("format_id"))
    if format_id is None and side == "sim":
        format_id = "sim_play_v1"
    experiment = _text(raw.get("experiment")) or ""
    count, first_t, duration = _policy_census(take_dir)
    return LabTakeMeta(
        day=day,
        take_id=take_dir.name,
        format_id=format_id,
        side=side,
        name=experiment or None,
        started_at=_iso_from_unix(first_t),
        started_unix=first_t,
        notes=experiment,
        sample_count=count,
        policy_count=count,
        duration_sec=duration,
        supported=format_id in SUPPORTED_FORMATS,
    )


def _experiment_of(take_dir: Path) -> str | None:
    """context.json ``experiment``. A v1 take with no context file returns None."""
    raw = _read_json_optional(take_dir / "context.json")
    return _text(raw.get("experiment")) if raw else None


def _policy_census(take_dir: Path) -> tuple[int, float | None, float | None]:
    """(row count, first wall-clock t, simulated seconds).

    Simulated seconds are (rows - 1) * the first row's period. Wall-clock gaps
    between rows are the PC catching up and are not the chart length.
    """
    folder = take_dir / "policy"
    count = 0
    first_t: float | None = None
    period: float | None = None
    if folder.is_dir():
        for path in sorted(folder.glob("part-*.jsonl")):
            try:
                handle = path.open("r", encoding="utf-8")
            except OSError:
                continue
            with handle:
                for line in handle:
                    if not line.strip():
                        continue
                    count += 1
                    if first_t is not None and period is not None:
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        row = {}
                    if not isinstance(row, dict):
                        continue
                    if first_t is None:
                        stamp = row.get("t")
                        if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
                            first_t = float(stamp)
                    if period is None:
                        step = row.get("t_period_us")
                        if isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0:
                            period = float(step)
    if period is None:
        period = 33333.0
    duration = (count - 1) * period / 1_000_000.0 if count > 1 else 0.0
    return count, first_t, duration


def _iso_from_unix(stamp: float | None) -> str | None:
    """Wall-clock UNIX seconds as a JST timestamp for the take list."""
    if stamp is None:
        return None
    try:
        return datetime.fromtimestamp(stamp, timezone(timedelta(hours=9))).isoformat(timespec="milliseconds")
    except (OverflowError, OSError, ValueError):
        return None


def _side_text(value: Any) -> str:
    return value if value in ("robot", "sim") else "robot"


def _summarize(take_dir: Path) -> dict[str, Any]:
    """One pass. Ratios use only samples where that flag was a real bool."""
    as_true = [0] * JOINT_COUNT
    as_n = [0] * JOINT_COUNT
    ina_true = [0] * JOINT_COUNT
    ina_n = [0] * JOINT_COUNT
    mag_counts: list[Counter[int]] = [Counter() for _ in range(JOINT_COUNT)]
    track_n = [0] * JOINT_COUNT
    track_sum = [0.0] * JOINT_COUNT
    track_max = [0.0] * JOINT_COUNT

    sample_count = 0
    parts_read = 0
    overrun_count = 0
    i2c_start: int | None = None
    i2c_end: int | None = None
    servo_true = 0
    servo_n = 0
    mode: str | None = None
    foot = _FootAcc()
    foot_left = _FootAcc()

    sensors = take_dir / "sensors"
    paths = part_paths(sensors, ".jsonl") if sensors.is_dir() else []
    parts_read = len(paths)
    for sample in _iter_rows(paths):
        sample_count += 1
        if sample.get("overrun") is True:
            overrun_count += 1
        i2c = _int_or_none(sample.get("i2c_err"))
        if i2c is not None:
            if i2c_start is None:
                i2c_start = i2c
            i2c_end = i2c
        if isinstance(sample.get("servo_ok"), bool):
            servo_n += 1
            if sample["servo_ok"]:
                servo_true += 1
        if isinstance(sample.get("mode"), str) and sample["mode"]:
            mode = sample["mode"]

        cmd = sample.get("cmd")
        corr = sample.get("corr")
        for index in range(JOINT_COUNT):
            _count_flag(sample.get("as_ok"), index, as_true, as_n)
            _count_flag(sample.get("ina_ok"), index, ina_true, ina_n)
            mag = _at_num_int(sample.get("mag"), index)
            if mag is not None:
                mag_counts[index][mag] += 1
            cmd_v = _at_num(cmd, index)
            corr_v = _at_num(corr, index)
            if cmd_v is None or corr_v is None:
                continue
            error = abs(corr_v - cmd_v)
            track_n[index] += 1
            track_sum[index] += error
            if error > track_max[index]:
                track_max[index] = error

        foot.add(sample.get("foot"))
        foot_left.add(sample.get("foot_left"))

    joints = []
    for index, name in enumerate(JOINT_NAMES):
        mag_mode = None
        if mag_counts[index]:
            mag_mode = sorted(mag_counts[index].items(), key=lambda item: (-item[1], item[0]))[0][0]
        joints.append(
            LabJointSummary(
                index=index,
                name=name,
                as_ok_ratio=_ratio(as_true[index], as_n[index]),
                ina_ok_ratio=_ratio(ina_true[index], ina_n[index]),
                mag_mode=mag_mode,
                tracking_mean_abs_deg=(track_sum[index] / track_n[index]) if track_n[index] else None,
                tracking_max_abs_deg=track_max[index] if track_n[index] else None,
                tracking_samples=track_n[index],
            )
        )

    delta = None
    if i2c_start is not None and i2c_end is not None:
        delta = i2c_end - i2c_start
    return {
        "sample_count_read": sample_count,
        "parts_read": parts_read,
        "overrun_count": overrun_count,
        "i2c_err_start": i2c_start,
        "i2c_err_end": i2c_end,
        "i2c_err_delta": delta,
        "servo_ok_ratio": _ratio(servo_true, servo_n),
        "mode": mode,
        "joints": joints,
        "foot": foot.finish(sample_count),
        "foot_left": foot_left.finish(sample_count),
    }


class _FootAcc:
    """Force range only while ok is true. A stored 0 kg with ok false is a gap."""

    def __init__(self) -> None:
        self.ok_n = 0
        self.seen = 0
        self.force_min: float | None = None
        self.force_max: float | None = None

    def add(self, payload: Any) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
            return
        self.seen += 1
        if not payload["ok"]:
            return
        self.ok_n += 1
        force = _float_or_none(payload.get("force_kg"))
        if force is None:
            return
        if self.force_min is None or force < self.force_min:
            self.force_min = force
        if self.force_max is None or force > self.force_max:
            self.force_max = force

    def finish(self, sample_count: int) -> LabFootSummary:
        # Prefer samples that actually carried a foot object. Fall back to the
        # take length only when the key was absent on every row.
        denom = self.seen or sample_count
        return LabFootSummary(
            ok_ratio=_ratio(self.ok_n, denom),
            force_min_kg=self.force_min,
            force_max_kg=self.force_max,
        )


def _project_row(sample: dict[str, Any], fields: list[str], joint: int | None) -> dict[str, Any]:
    row: dict[str, Any] = {"t": float(sample["t"])}
    for name in fields:
        if name == "foot_force_kg":
            row[name] = _foot_force(sample.get("foot"))
        elif name == "foot_left_force_kg":
            row[name] = _foot_force(sample.get("foot_left"))
        elif joint is None:
            row[name] = None
        else:
            row[name] = _at_num(sample.get(name), joint)
    return row


def _foot_force(payload: Any) -> float | None:
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return None
    return _float_or_none(payload.get("force_kg"))


def _downsample(rows: list[dict[str, Any]], max_points: int) -> tuple[list[dict[str, Any]], bool]:
    """Equal-count buckets. A bucket with no numeric values stays null."""
    if len(rows) <= max_points:
        return rows, False
    keys = [key for key in rows[0] if key != "t"]
    reduced: list[dict[str, Any]] = []
    span = len(rows) / max_points
    for bucket in range(max_points):
        start = int(bucket * span)
        end = int((bucket + 1) * span)
        if end <= start:
            end = min(start + 1, len(rows))
        chunk = rows[start:end]
        if not chunk:
            continue
        point: dict[str, Any] = {"t": chunk[len(chunk) // 2]["t"]}
        for key in keys:
            nums = [value for value in (row.get(key) for row in chunk) if isinstance(value, float)]
            point[key] = (sum(nums) / len(nums)) if nums else None
        reduced.append(point)
    return reduced, True


def _clean_fields(fields: list[str]) -> list[str]:
    requested: list[str] = []
    for raw in fields:
        for piece in raw.split(","):
            name = piece.strip()
            if not name:
                continue
            if name not in SERIES_FIELDS:
                raise LabError(400, ERR_BAD_FIELD)
            if name not in requested:
                requested.append(name)
    if not requested:
        raise LabError(400, ERR_BAD_FIELD)
    return requested


def _iter_sensor_rows(take_dir: Path) -> Iterator[dict[str, Any]]:
    sensors = take_dir / "sensors"
    if not sensors.is_dir():
        return
    yield from _iter_rows(part_paths(sensors, ".jsonl"))


def iter_event_lines(take_dir: Path) -> Iterator[str]:
    events = take_dir / "events"
    if not events.is_dir():
        return
    for path in part_paths(events, ".log"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                yield stripped


def _iter_rows(paths: list[Path]) -> Iterator[dict[str, Any]]:
    for path in paths:
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    yield payload


def part_paths(folder: Path, suffix: str) -> list[Path]:
    paths = [path for path in folder.glob(f"part-*{suffix}") if path.is_file()]
    paths.sort(key=_part_index)
    return paths


def _part_index(path: Path) -> int:
    match = _PART_RE.search(path.name)
    return int(match.group(1)) if match else 0


def split_event(line: str) -> tuple[str | None, str]:
    match = _EVENT_RE.match(line)
    if not match:
        return None, line
    return match.group(1), match.group(2).strip()


def _count_flag(payload: Any, index: int, true_counts: list[int], seen_counts: list[int]) -> None:
    if not isinstance(payload, list) or index >= len(payload):
        return
    flag = payload[index]
    if not isinstance(flag, bool):
        return
    seen_counts[index] += 1
    if flag:
        true_counts[index] += 1


def _at_num(payload: Any, index: int) -> float | None:
    if not isinstance(payload, list) or index >= len(payload):
        return None
    return _float_or_none(payload[index])


def _at_num_int(payload: Any, index: int) -> int | None:
    if not isinstance(payload, list) or index >= len(payload):
        return None
    return _int_or_none(payload[index])


def _read_json_optional(path: Path) -> dict[str, Any] | None:
    """JSON object, or None when the file is missing or not an object.

    Listing must not fail just because an older take has no context.json.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LabError(404, ERR_NOT_FOUND) from exc
    if not isinstance(payload, dict):
        raise LabError(404, ERR_NOT_FOUND)
    return payload


def parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _ratio(numer: int, denom: int) -> float | None:
    if denom <= 0:
        return None
    return numer / denom


def _digits(name: str, width: int) -> bool:
    return len(name) == width and name.isdigit()


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_float_or_none(value: Any) -> float | None:
    if isinstance(value, float):
        return value
    return None
