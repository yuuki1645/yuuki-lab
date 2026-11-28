# -*- coding: utf-8 -*-
"""Anomaly detection, health map and range queries for one take.

Reads the cached columns from lab_columns. Results are plain data: kind
codes, sample indices and numbers. The browser owns every sentence, so the
Japanese copy lives in one place (frontend ``labels.ts``).

Severity levels used everywhere:

    0 ok, 1 info / no data, 2 warn, 3 crit

Time axis: ``offset`` is seconds since the first sensor row of the take
(UNIX ``t`` minus ``t0``). Events and commands are moved onto that axis, so
one number lines up every chart, marker and table row.

The detectors are generic for core_take_v1. They key off flags and physics
(output enabled, command settled, rail powered) rather than any one take,
so a joint that is simply unpowered or a leg that is not plugged in reads as
"no data", not as a failure.
"""

from __future__ import annotations

import json
import math
import re
from array import array
from bisect import bisect_left, bisect_right
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterator

from take_view.schemas import LabTakeMeta
from take_view.lab_columns import (
    CORNERS,
    FEET,
    JOINT_COUNT,
    ChannelError,
    TakeColumns,
    all_channels,
    load_columns,
    parse_channel,
)
from take_view.lab_policy import POLICY_THRESHOLDS, apply_policy_flags, apply_sim_flags
from take_view.lab_takes import (
    ERR_BAD_FIELD,
    JOINT_NAMES,
    LabError,
    iter_event_lines,
    parse_iso,
    part_paths,
    resolve_supported_take,
    split_event,
)

# Detector thresholds. Returned to the browser so every flag is explainable.
THRESHOLDS: dict[str, float] = {
    # Tracking is judged only while the axis PWM is on and the command has
    # been steady for settle_sec, so a servo that is still travelling to a
    # new target is not called an error.
    "settle_sec": 0.6,
    "track_warn_deg": 8.0,
    "track_crit_deg": 15.0,
    # A constant offset (median of corr - cmd) is reported once per joint
    # and removed before judging transient tracking error.
    "offset_warn_deg": 5.0,
    "offset_crit_deg": 15.0,
    "offset_min_samples": 20,
    # Encoder jump: one-row angle change that no command explains.
    "jump_deg": 30.0,
    "jump_max_gap_sec": 0.3,
    # INA226 current per axis.
    "amp_warn": 1.5,
    "amp_crit": 2.5,
    # A rail counts as powered above volt_powered. A sag is a powered rail
    # dipping below volt_sag_ratio of that joint's powered median and coming
    # back within volt_sag_max_sec. Below volt_off_ratio of the median, or a
    # longer dip, is the supply being switched off, not a brownout.
    "volt_powered": 5.0,
    "volt_sag_ratio": 0.85,
    "volt_off_ratio": 0.3,
    "volt_sag_max_sec": 2.0,
    # PC receive gaps.
    "rx_gap_warn_sec": 0.25,
    "rx_gap_crit_sec": 1.0,
    "jitter_warn_us": 10000.0,
    # New I2C failures inside a sliding one-second window.
    "i2c_crit_per_sec": 5.0,
    # Each foot corner is rated 2 kg (schema.md).
    "foot_rated_kg": 2.0,
    # Flags closer than this merge into one interval.
    "merge_gap_sec": 1.0,
}
# Policy limits live next to the detector that uses them.
THRESHOLDS.update(POLICY_THRESHOLDS)

# Kind codes. Index 0 means "nothing" in the per-bucket kind arrays.
KINDS: tuple[str, ...] = (
    "",
    "nodata",
    "dropout",
    "magnet",
    "no_map",
    "jump",
    "tracking",
    "track_offset",
    "overcurrent",
    "undervolt",
    "seq_drop",
    "seq_reset",
    "rx_gap",
    "overrun",
    "jitter",
    "i2c",
    "servo_lost",
    "foot_lost",
    "corner_missing",
    "foot_saturated",
    "event_error",
    "abnormal_stop",
    # Policy trace (core_take_v2). Absent on v1, so these indexes stay unused.
    "policy_safety",
    "policy_reason",
    "policy_flag",
    "policy_stale",
    "policy_clip",
    "policy_diverge",
    # Playback only. The command was not clipped; the real robot would have clipped it.
    "sim_envelope",
    "sim_tilt",
    # SM105BL: the servo's own angle is missing. Not an AS5600 dropout.
    "servo_fb",
)
KIND_INDEX = {name: index for index, name in enumerate(KINDS)}

# Health map rows: one per logical axis, then firmware-wide rows.
SYSTEM_LANES: tuple[str, ...] = ("link", "timing", "i2c", "servo", "foot", "foot_left", "events")
LANES: tuple[str, ...] = tuple(f"j{joint}" for joint in range(JOINT_COUNT)) + SYSTEM_LANES
RIGHT_LEG = range(0, 5)
LEFT_LEG = range(5, 10)

DEFAULT_BUCKETS = 800
MAX_BUCKETS = 2400
MAX_INTERVALS = 400
MAX_EVENTS = 5000
MAX_COMMANDS = 20000
MAX_CHANNELS = 64
MAX_ROWS = 500
DEFAULT_TARGET_PERIOD_US = 50000.0

# Stop reasons that are a normal end of a recording (schema.md).
_NORMAL_STOPS = frozenset({"USB \u5207\u65ad", "\u30c4\u30fc\u30eb\u7d42\u4e86"})
# Words that make a stop reason a hard failure: エラー / 中断 / プロセス終了.
_CRIT_STOP_RE = re.compile("\u30a8\u30e9\u30fc|\u4e2d\u65ad|\u30d7\u30ed\u30bb\u30b9\u7d42\u4e86")
# Event screen lines. ERROR / エラー / 過電流 are errors.
_EVENT_ERROR_RE = re.compile("ERROR|\u30a8\u30e9\u30fc|\u904e\u96fb\u6d41", re.IGNORECASE)
# 欠測なし = "no longer missing", a recovery line.
_EVENT_RECOVER_RE = re.compile("\u6b20\u6e2c\u306a\u3057")
# 欠測 / overrun / I2C / 切断 are warnings.
_EVENT_WARN_RE = re.compile("\u6b20\u6e2c|overrun|I2C|\u5207\u65ad", re.IGNORECASE)
# 関節N names a logical axis in event text.
_EVENT_JOINT_RE = re.compile("\u95a2\u7bc0\\s*(\\d+)")

ERR_NEED_POINT = "index \u304b t \u3092\u6307\u5b9a\u3057\u3066\u304f\u3060\u3055\u3044"
ERR_EMPTY = "\u3053\u306e take \u306b\u306f\u30bb\u30f3\u30b5\u30fc\u884c\u304c\u3042\u308a\u307e\u305b\u3093"


# ---------------------------------------------------------------------------
# Public API (routers call these)
# ---------------------------------------------------------------------------


def get_analysis(day: str, take_id: str, *, buckets: int = DEFAULT_BUCKETS, side: str | None = None) -> dict[str, Any]:
    """Everything the workbench needs on open: health map, findings, stats.

    Detection runs once per parsed take and is memoised on the columns.
    The bucketed health map is memoised per bucket count.
    """
    columns, take_dir, meta = _open(day, take_id, side)
    buckets = max(10, min(MAX_BUCKETS, int(buckets)))
    detection = _detection(columns, take_dir, meta)
    with columns.memo_lock:
        key = ("health", buckets)
        health = columns.memo.get(key)
        if health is None:
            health = _health(columns, detection["flags"], buckets)
            columns.memo[key] = health
    return {
        "day": day,
        "take_id": take_id,
        # meta rides along so the workbench needs no second pass over sensors.
        "meta": meta.model_dump(),
        "tail_pending": bool(meta.recording or meta.open_parts),
        "t0": columns.t0,
        "duration_sec": columns.duration,
        "sample_count": columns.n,
        "parts_read": len(columns.paths),
        "thresholds": THRESHOLDS,
        "kinds": list(KINDS),
        "lanes": list(LANES),
        "joint_names": _joint_names(columns),
        "health": health,
        "findings": detection["findings"],
        "joint_stats": detection["joint_stats"],
        "system_stats": detection["system_stats"],
        "out_spans": detection["out_spans"],
        "events": detection["events"],
        "events_total": detection["events_total"],
        "commands": detection["commands"],
        "commands_total": detection["commands_total"],
        # Native pad counts. None when this take never recorded a gamepad.
        # The chart's pad.* channels are folded onto sensor rows separately.
        "gamepad": columns.gamepad_summary(),
        # Native policy counts. None when policy/ was never written (every v1 take).
        "policy": _policy_summary(columns),
        "context": _context_brief(columns),
    }


def get_window(
    day: str,
    take_id: str,
    *,
    channels: list[str],
    t_from: float | None,
    t_to: float | None,
    max_points: int,
    side: str | None = None,
) -> dict[str, Any]:
    """Chart data for a time range.

    Up to ``max_points`` rows come back untouched (``mode: raw``). Beyond
    that the range is cut into equal-time buckets and each bucket returns
    min, max and mean (``mode: envelope``). Min/max is what keeps a single
    spike visible when zoomed out; a plain mean would hide it.
    """
    columns, take_dir, meta = _open(day, take_id, side)
    names = _clean_channels(channels)
    t_from, t_to = _clamp_range(columns, t_from, t_to)
    arrays = {name: _channel(columns, take_dir, meta, name) for name in names}
    offsets = columns.t_off
    count = columns.n
    lo = bisect_left(offsets, t_from)
    hi = bisect_right(offsets, t_to)
    # One extra row on each side so lines run to the plot edges.
    lo = max(0, lo - 1)
    hi = min(count, hi + 1)
    max_points = max(10, int(max_points))
    base: dict[str, Any] = {"from": t_from, "to": t_to, "channels": names, "sample_count": hi - lo}

    if hi - lo <= max_points:
        base.update(
            mode="raw",
            t=[round(offsets[index], 4) for index in range(lo, hi)],
            index=list(range(lo, hi)),
            series={name: {"v": [_r(values[index]) for index in range(lo, hi)]} for name, values in arrays.items()},
        )
        return base

    bucket_count = max(1, max_points // 2)
    width = (t_to - t_from) / bucket_count
    times: list[float] = []
    first_index: list[int | None] = []
    series: dict[str, dict[str, list[float | None]]] = {
        name: {"min": [], "max": [], "mean": []} for name in names
    }
    edge = bisect_left(offsets, t_from, lo, hi)
    for bucket in range(bucket_count):
        upper = t_from + (bucket + 1) * width
        end = bisect_right(offsets, t_to, lo, hi) if bucket == bucket_count - 1 else bisect_left(offsets, upper, lo, hi)
        times.append(round(t_from + (bucket + 0.5) * width, 4))
        first_index.append(edge if end > edge else None)
        for name, values in arrays.items():
            target = series[name]
            finite = [value for value in values[edge:end] if value == value]
            if finite:
                target["min"].append(_r(min(finite)))
                target["max"].append(_r(max(finite)))
                target["mean"].append(_r(sum(finite) / len(finite)))
            else:
                target["min"].append(None)
                target["max"].append(None)
                target["mean"].append(None)
        edge = end
    base.update(mode="envelope", t=times, index=first_index, bucket_sec=width, series=series)
    return base


def get_range_stats(
    day: str,
    take_id: str,
    *,
    channels: list[str],
    t_from: float | None,
    t_to: float | None,
    side: str | None = None,
) -> dict[str, Any]:
    """Descriptive statistics per channel for the rows inside [from, to].

    argmin / argmax come with their sample index so the UI can jump there.
    """
    columns, take_dir, meta = _open(day, take_id, side)
    names = _clean_channels(channels)
    t_from, t_to = _clamp_range(columns, t_from, t_to)
    offsets = columns.t_off
    lo = bisect_left(offsets, t_from)
    hi = bisect_right(offsets, t_to)
    stats: dict[str, Any] = {}
    for name in names:
        values = _channel(columns, take_dir, meta, name)
        stats[name] = _describe_range(values, lo, hi, offsets)
    span = offsets[hi - 1] - offsets[lo] if hi - lo >= 2 else 0.0
    return {
        "from": t_from,
        "to": t_to,
        "start_index": lo,
        "end_index": hi - 1,
        "sample_count": hi - lo,
        "rate_hz": (hi - lo - 1) / span if span > 0 else None,
        "stats": stats,
    }


def get_rows(
    day: str, take_id: str, *, channels: list[str], start: int, count: int, side: str | None = None
) -> dict[str, Any]:
    """Untouched rows by index for the data table. Columnar to stay small."""
    columns, take_dir, meta = _open(day, take_id, side)
    names = _clean_channels(channels)
    total = columns.n
    if total == 0:
        raise LabError(404, ERR_EMPTY)
    count = max(1, min(MAX_ROWS, int(count)))
    start = max(0, min(total - 1, int(start)))
    end = min(total, start + count)
    offsets = columns.t_off
    seq = columns.seq
    arrays = {name: _channel(columns, take_dir, meta, name) for name in names}
    return {
        "channels": names,
        "start": start,
        "end": end,
        "total": total,
        "index": list(range(start, end)),
        "t": [round(offsets[index], 4) for index in range(start, end)],
        "seq": [int(seq[index]) if seq[index] >= 0 else None for index in range(start, end)],
        "series": {name: [_r(values[index]) for index in range(start, end)] for name, values in arrays.items()},
    }


def get_sample(
    day: str, take_id: str, *, index: int | None, t: float | None, side: str | None = None
) -> dict[str, Any]:
    """One row exactly as stored, plus where it lives on disk and its flags."""
    columns, take_dir, meta = _open(day, take_id, side)
    total = columns.n
    if total == 0:
        raise LabError(404, ERR_EMPTY)
    if index is None and t is None:
        raise LabError(400, ERR_NEED_POINT)
    if index is None:
        index = _nearest_index(columns.t_off, float(t or 0.0))
    index = max(0, min(total - 1, int(index)))
    detection = _detection(columns, take_dir, meta)
    flags: _Flags = detection["flags"]
    lane_flags = {
        lane: {"sev": flags.sev[lane][index], "kind": KINDS[flags.kind[lane][index]]}
        for lane in flags.lanes
        if flags.sev[lane][index]
    }
    part, line = columns.location(index)
    raw_line = columns.read_line(index)
    row = None
    if raw_line is not None:
        try:
            parsed = json.loads(raw_line)
            row = parsed if isinstance(parsed, dict) else None
        except ValueError:
            row = None
    return {
        "index": index,
        "total": total,
        "t": columns.t[index],
        "t_offset": columns.t_off[index],
        "part": part,
        "line": line,
        # Exact text from disk (float formatting included) for copy / audit.
        "raw_line": raw_line,
        "row": row,
        "flags": lane_flags,
        # Pad row held at this sensor time. Null before the pad file starts.
        "gamepad": columns.pad_at(columns.t[index]),
        # Nearest policy row on the policy file's own clock. Null on v1.
        "policy": None
        if columns.policy is None
        else columns.policy.at(columns.t[index], columns.t0),
    }


def export_csv(
    day: str,
    take_id: str,
    *,
    channels: list[str],
    t_from: float | None,
    t_to: float | None,
    side: str | None = None,
) -> tuple[str, Iterator[str]]:
    """(filename, line iterator) for the rows inside [from, to].

    No channel list means every channel. Gaps are empty cells, never 0.
    """
    columns, take_dir, meta = _open(day, take_id, side)
    names = (
        _clean_channels(channels)
        if any(item.strip() for item in channels)
        else all_channels(columns.pad_n > 0, bool(columns.policy is not None and columns.policy.n))
    )
    t_from, t_to = _clamp_range(columns, t_from, t_to)
    offsets = columns.t_off
    lo = bisect_left(offsets, t_from)
    hi = bisect_right(offsets, t_to)
    arrays = [_channel(columns, take_dir, meta, name) for name in names]
    stamps = columns.t

    def lines() -> Iterator[str]:
        yield "index,t_unix,t_offset_sec," + ",".join(names) + "\n"
        chunk: list[str] = []
        for row in range(lo, hi):
            cells = [str(row), f"{stamps[row]:.6f}", f"{offsets[row]:.6f}"]
            cells.extend("" if values[row] != values[row] else format(values[row], ".10g") for values in arrays)
            chunk.append(",".join(cells))
            if len(chunk) >= 500:
                yield "\n".join(chunk) + "\n"
                chunk = []
        if chunk:
            yield "\n".join(chunk) + "\n"

    filename = f"{take_id}_{t_from:.1f}-{t_to:.1f}s.csv"
    return filename, lines()


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def _open(day: str, take_id: str, side: str | None = None) -> tuple[TakeColumns, Path, LabTakeMeta]:
    take_dir, meta = resolve_supported_take(day, take_id, side)
    sensors = take_dir / "sensors"
    paths = part_paths(sensors, ".jsonl") if sensors.is_dir() else []
    return load_columns(take_dir, paths), take_dir, meta


def _joint_names(columns: TakeColumns) -> list[str]:
    """Names from context.json when the take stored them, else the v1 list."""
    context = columns.context
    if context is not None and context.present:
        return list(context.joint_names)
    return list(JOINT_NAMES)


def _policy_summary(columns: TakeColumns) -> dict[str, Any] | None:
    table = columns.policy
    if table is None or table.n == 0:
        return None
    summary = table.summary(columns.t0)
    if columns.sim_clock:
        # summary() uses wall-clock t. A playback's wall gaps are the PC,
        # not the 30 Hz the file declares, so replace the rate.
        duration = columns.duration
        summary["rate_hz"] = (columns.n - 1) / duration if duration > 0 else None
        summary["clock"] = "sim"
        summary["sim_sec"] = duration
    return summary


def _context_brief(columns: TakeColumns) -> dict[str, Any] | None:
    """Contract excerpt. Sent when the take has a context file or a policy trace."""
    context = columns.context
    table = columns.policy
    if context is None:
        return None
    if not context.present and (table is None or table.n == 0):
        return None
    return context.brief()


def _channel(columns: TakeColumns, take_dir: Path, meta: LabTakeMeta, name: str) -> array:
    """Values for one channel id, including the detector verdict ``j<N>.sev``.

    sev per row: 0 ok, 1 no data, 2 warn, 3 crit, exactly what the health
    map shows for that joint. Everything else comes from the columns.
    """
    if not name.endswith(".sev"):
        return columns.values(name)
    key = ("sev_values", name)
    cached = columns.memo.get(key)
    if cached is not None:
        return cached
    _, joint, _ = parse_channel(name)
    flags: _Flags = _detection(columns, take_dir, meta)["flags"]
    # Convert element by element: array("d", bytearray) would reinterpret
    # the raw bytes as doubles instead.
    values = array("d", (float(level) for level in flags.sev[f"j{joint}"]))
    # Plain dict store: a racing duplicate build is harmless and memo_lock
    # is not re-entrant (_detection above already took it).
    columns.memo[key] = values
    return values


def _clean_channels(channels: list[str]) -> list[str]:
    names: list[str] = []
    for raw in channels:
        for piece in raw.split(","):
            name = piece.strip()
            if not name:
                continue
            try:
                parse_channel(name)
            except ChannelError as exc:
                raise LabError(400, ERR_BAD_FIELD) from exc
            if name not in names:
                names.append(name)
    if not names or len(names) > MAX_CHANNELS:
        raise LabError(400, ERR_BAD_FIELD)
    return names


def _clamp_range(columns: TakeColumns, t_from: float | None, t_to: float | None) -> tuple[float, float]:
    """Missing bounds mean the whole take. A reversed range is swapped."""
    end = columns.duration
    start = 0.0 if t_from is None or not math.isfinite(t_from) else float(t_from)
    stop = end if t_to is None or not math.isfinite(t_to) else float(t_to)
    if stop < start:
        start, stop = stop, start
    if stop - start < 1e-3:
        stop = start + 1e-3
    return start, stop


def _nearest_index(offsets: array, target: float) -> int:
    pos = bisect_left(offsets, target)
    if pos <= 0:
        return 0
    if pos >= len(offsets):
        return len(offsets) - 1
    before = offsets[pos - 1]
    after = offsets[pos]
    return pos - 1 if target - before <= after - target else pos


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


class _Flags:
    """Per-sample severity for every lane plus the raw flags per (kind, lane).

    ``sev[lane][i]`` is the worst severity at row i, ``kind[lane][i]`` the
    kind code that set it. ``groups`` keeps (index, severity, value) for
    turning runs of flags into findings.
    """

    def __init__(self, count: int, lanes: tuple[str, ...] | None = None) -> None:
        self.count = count
        # v2 adds a "policy" lane. v1 keeps the original rows.
        self.lanes = LANES if lanes is None else lanes
        self.sev = {lane: bytearray(count) for lane in self.lanes}
        self.kind = {lane: bytearray(count) for lane in self.lanes}
        self.groups: dict[tuple[str, str], list[tuple[int, int, float]]] = {}

    def add(self, kind: str, lane: str, index: int, sev: int, value: float = math.nan) -> None:
        row = self.sev[lane]
        if sev > row[index]:
            row[index] = sev
            self.kind[lane][index] = KIND_INDEX[kind]
        bucket = self.groups.get((kind, lane))
        if bucket is None:
            bucket = []
            self.groups[(kind, lane)] = bucket
        bucket.append((index, sev, value))


def _detection(columns: TakeColumns, take_dir: Path, meta: LabTakeMeta) -> dict[str, Any]:
    with columns.memo_lock:
        cached = columns.memo.get("detect")
        if cached is None:
            cached = _detect(columns, take_dir, meta)
            columns.memo["detect"] = cached
        return cached


def _detect(columns: TakeColumns, take_dir: Path, meta: LabTakeMeta) -> dict[str, Any]:
    # No sensor file: do not run encoder / link / foot detectors on blank rows.
    if columns.sim_clock:
        return _detect_playback(columns, take_dir, meta)
    count = columns.n
    lanes = LANES
    if columns.policy is not None and columns.policy.n:
        lanes = LANES + ("policy",)
    flags = _Flags(count, lanes)
    online = (_leg_online(columns, RIGHT_LEG), _leg_online(columns, LEFT_LEG))
    extras: list[dict[str, Any]] = []
    per_joint: list[dict[str, Any]] = []

    for joint in range(JOINT_COUNT):
        leg = online[0] if joint in RIGHT_LEG else online[1]
        moving, on = _motion_masks(columns, joint)
        presence = _detect_presence(columns, flags, joint, leg, _feedback_servo(columns, joint))
        jumps = _detect_jumps(columns, flags, joint, moving, on)
        tracking, offset_finding = _detect_tracking(columns, flags, joint, moving, on)
        if offset_finding is not None:
            extras.append(offset_finding)
        power = _detect_power(columns, flags, joint, _feedback_servo(columns, joint))
        per_joint.append(
            {
                "presence": presence,
                "jumps": jumps,
                "tracking": tracking,
                "power": power,
                "out_ratio": (sum(on) / count) if count else None,
                "online_ratio": (sum(leg) / count) if count else None,
            }
        )

    target_period = _detect_link_and_timing(columns, flags)
    i2c = _detect_i2c(columns, flags)
    _detect_servo(columns, flags)
    for foot in FEET:
        _detect_foot(columns, flags, foot)

    apply_policy_flags(columns, flags)
    events, events_total = _load_events(take_dir, columns)
    commands, commands_total = _load_commands(take_dir, columns)
    _detect_events(columns, flags, events)
    stop = _detect_stop(columns, flags, meta)
    if stop is not None:
        extras.append(stop)

    findings = _build_findings(columns, flags, extras, events)
    joint_stats = _joint_stats(columns, per_joint, findings)
    system_stats = _system_stats(columns, flags, findings, target_period, i2c)
    return {
        "flags": flags,
        "findings": findings,
        "joint_stats": joint_stats,
        "system_stats": system_stats,
        "out_spans": [_out_spans(columns, joint) for joint in range(JOINT_COUNT)],
        "events": events,
        "events_total": events_total,
        "commands": commands,
        "commands_total": commands_total,
    }


def _detect_playback(columns: TakeColumns, take_dir: Path, meta: LabTakeMeta) -> dict[str, Any]:
    """Playback findings. Sensor lanes stay clear because no encoder was recorded.

    ``meta`` is unused; the signature matches ``_detect`` so the caller can
    branch without a second shape.
    """
    del meta
    flags = _Flags(columns.n, LANES + ("policy",))
    apply_policy_flags(columns, flags)
    apply_sim_flags(columns, flags)
    events, events_total = _load_events(take_dir, columns)
    commands, commands_total = _load_commands(take_dir, columns)
    findings = _build_findings(columns, flags, [], events)
    empty = {"online": 0, "as_ok": 0, "dropout": 0, "mag_counts": {}}
    per_joint = [
        {
            "presence": empty,
            "jumps": 0,
            "tracking": {},
            "power": {},
            "out_ratio": None,
            "online_ratio": None,
        }
        for _ in range(JOINT_COUNT)
    ]
    periods = [value for value in columns.sys["period_us"] if value == value and value > 0]
    target = periods[len(periods) // 2] if periods else None
    i2c = {"start": None, "end": None, "max_per_sec": None}
    return {
        "flags": flags,
        "findings": findings,
        "joint_stats": _joint_stats(columns, per_joint, findings),
        "system_stats": _system_stats(columns, flags, findings, target, i2c),
        "out_spans": [_out_spans(columns, joint) for joint in range(JOINT_COUNT)],
        "events": events,
        "events_total": events_total,
        "commands": commands,
        "commands_total": commands_total,
    }


def _leg_online(columns: TakeColumns, joints: range) -> bytearray:
    """1 where any joint of the leg reported an encoder or INA reading.

    A leg board that is not connected leaves every flag false. That is
    "no data" for its joints, not five simultaneous sensor failures.
    """
    out = bytearray(columns.n)
    as_ok = [columns.joint_flag["as_ok"][joint] for joint in joints]
    ina_ok = [columns.joint_flag["ina_ok"][joint] for joint in joints]
    for index in range(columns.n):
        for flags in as_ok:
            if flags[index] == 1:
                out[index] = 1
                break
        else:
            for flags in ina_ok:
                if flags[index] == 1:
                    out[index] = 1
                    break
    return out


def _motion_masks(columns: TakeColumns, joint: int) -> tuple[bytearray, bytearray]:
    """(moving, on) per row for one axis.

    on: the PWM for this axis is enabled (bit of out_mask).
    moving: within settle_sec of a command change or of the output turning
    on. The servo is still travelling there, so error and jumps are expected.
    """
    count = columns.n
    offsets = columns.t_off
    cmd = columns.joint_float["cmd"][joint]
    out = columns.values(f"j{joint}.out")
    settle = THRESHOLDS["settle_sec"]
    moving = bytearray(count)
    on = bytearray(count)
    last_change = -math.inf
    prev_cmd = math.nan
    prev_on = False
    for index in range(count):
        now = offsets[index]
        value = cmd[index]
        is_on = out[index] == 1.0
        if value == value and prev_cmd == prev_cmd and abs(value - prev_cmd) > 0.05:
            last_change = now
        if is_on and not prev_on:
            last_change = now
        if value == value:
            prev_cmd = value
        prev_on = is_on
        if is_on:
            on[index] = 1
        if now - last_change < settle:
            moving[index] = 1
    return moving, on


def _feedback_servo(columns: TakeColumns, joint: int) -> bool:
    """True when this axis is an SM105BL and has no AS5600 or INA226.

    The angle, when it arrives, is the servo's own feedback in ``corr``
    with ``as_ok``. ``mag`` 255, ``map_ok`` false and a silent current
    reading are how that joint is recorded, not a broken encoder.
    A take that never wrote ``servo`` keeps the older sensor path.
    """
    context = getattr(columns, "context", None)
    servos = getattr(context, "servos", None) if context is not None else None
    if not servos or joint >= len(servos):
        return False
    return servos[joint] == "SM105BL"


def _detect_presence(
    columns: TakeColumns,
    flags: _Flags,
    joint: int,
    leg: bytearray,
    feedback: bool = False,
) -> dict[str, Any]:
    """Missing angle, magnet status and missing calibration for one axis.

    ``feedback`` is an SM105BL. There is no magnet and no calibration map.
    ``as_ok`` false means the servo did not send its present angle.
    """
    lane = f"j{joint}"
    as_ok = columns.joint_flag["as_ok"][joint]
    map_ok = columns.joint_flag["map_ok"][joint]
    mag = columns.joint_int["mag"][joint]
    mag_counts: Counter[int] = Counter()
    online = 0
    ok = 0
    for index in range(columns.n):
        if not leg[index]:
            flags.add("nodata", lane, index, 1)
            continue
        online += 1
        if feedback:
            # mag 255 and map_ok false are permanent on this servo. Ignore them.
            if as_ok[index] != 1:
                flags.add("servo_fb", lane, index, 3)
                continue
            ok += 1
            continue
        code = mag[index]
        if code > 0:
            mag_counts[code] += 1
        if as_ok[index] != 1:
            flags.add("dropout", lane, index, 3, float(code) if code >= 0 else math.nan)
            continue
        ok += 1
        if code in (1, 2, 3, 4):
            flags.add("magnet", lane, index, 2, float(code))
        if map_ok[index] == 0:
            flags.add("no_map", lane, index, 1)
    return {
        "online": online,
        "as_ok": ok,
        "dropout": online - ok,
        "mag_counts": {str(code): number for code, number in sorted(mag_counts.items())},
    }


def _detect_jumps(columns: TakeColumns, flags: _Flags, joint: int, moving: bytearray, on: bytearray) -> int:
    """Angle steps between two consecutive readings that no command explains.

    Uses corr (command space) when both rows have it, else the raw encoder
    angle with 360 degree wrap removed. Skipped while a commanded move is
    still settling.
    """
    lane = f"j{joint}"
    raw = columns.joint_float["raw"][joint]
    corr = columns.joint_float["corr"][joint]
    offsets = columns.t_off
    limit = THRESHOLDS["jump_deg"]
    max_gap = THRESHOLDS["jump_max_gap_sec"]
    found = 0
    prev = -1
    for index in range(columns.n):
        angle = raw[index]
        if angle != angle:
            continue
        if prev >= 0 and offsets[index] - offsets[prev] <= max_gap and not (on[index] and moving[index]):
            now_corr = corr[index]
            before_corr = corr[prev]
            if now_corr == now_corr and before_corr == before_corr:
                step = abs(now_corr - before_corr)
            else:
                step = abs((angle - raw[prev] + 180.0) % 360.0 - 180.0)
            if step >= limit:
                flags.add("jump", lane, index, 2, step)
                found += 1
        prev = index
    return found


def _detect_tracking(
    columns: TakeColumns,
    flags: _Flags,
    joint: int,
    moving: bytearray,
    on: bytearray,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Commanded vs measured angle while driven and settled.

    Two separate findings: a constant offset (median error, typically a
    calibration or horn mounting issue) and transient deviation from that
    offset (stall, load, slipping), so one does not drown the other.
    """
    lane = f"j{joint}"
    err = columns.values(f"j{joint}.err")
    settled: list[int] = [
        index for index in range(columns.n) if on[index] and not moving[index] and err[index] == err[index]
    ]
    signed = [err[index] for index in settled]
    off_abs = [abs(err[index]) for index in range(columns.n) if not on[index] and err[index] == err[index]]
    enough = len(signed) >= THRESHOLDS["offset_min_samples"]
    median = _median(signed) if enough else 0.0
    assert median is not None

    warn = THRESHOLDS["track_warn_deg"]
    crit = THRESHOLDS["track_crit_deg"]
    for index in settled:
        deviation = abs(err[index] - median)
        if deviation >= crit:
            flags.add("tracking", lane, index, 3, err[index])
        elif deviation >= warn:
            flags.add("tracking", lane, index, 2, err[index])

    abs_sorted = sorted(abs(value) for value in signed)
    max_index = max(settled, key=lambda index: abs(err[index])) if settled else None
    stats = {
        "samples": len(signed),
        "median_deg": median if enough else None,
        "mean_abs_deg": (sum(abs_sorted) / len(abs_sorted)) if abs_sorted else None,
        "p95_abs_deg": _percentile(abs_sorted, 0.95),
        "max_abs_deg": abs_sorted[-1] if abs_sorted else None,
        "max_index": max_index,
        "off_mean_abs_deg": (sum(off_abs) / len(off_abs)) if off_abs else None,
    }

    offset_finding = None
    if enough and abs(median) >= THRESHOLDS["offset_warn_deg"]:
        severity = 3 if abs(median) >= THRESHOLDS["offset_crit_deg"] else 2
        offset_finding = _single_finding(
            columns,
            kind="track_offset",
            lane=lane,
            severity=severity,
            start=settled[0],
            end=settled[-1],
            sample_count=len(settled),
            peak_index=max_index if max_index is not None else settled[0],
            peak_value=median,
            detail={"median_deg": median, "samples": len(settled)},
        )
    return stats, offset_finding


def _detect_power(columns: TakeColumns, flags: _Flags, joint: int, feedback: bool = False) -> dict[str, Any]:
    """Over-current and rail sag on one axis's INA226.

    An SM105BL has no INA226. The file may still carry amp 0 and a bus
    volt; those are not a current sensor and must not become findings.
    """
    if feedback:
        return {
            "amp_mean": None,
            "amp_p99": None,
            "amp_max": None,
            "amp_max_index": None,
            "volt_powered_median": None,
            "volt_powered_min": None,
            "volt_sag_samples": 0,
            "watt_max": None,
        }
    lane = f"j{joint}"
    amp = columns.joint_float["amp"][joint]
    volt = columns.joint_float["volt"][joint]
    watt = columns.joint_float["watt"][joint]
    ina_ok = columns.joint_flag["ina_ok"][joint]
    warn = THRESHOLDS["amp_warn"]
    crit = THRESHOLDS["amp_crit"]
    amps: list[float] = []
    max_amp = -math.inf
    max_amp_index: int | None = None
    for index in range(columns.n):
        value = amp[index]
        if value != value or ina_ok[index] == 0:
            continue
        amps.append(value)
        if value > max_amp:
            max_amp = value
            max_amp_index = index
        if value >= crit:
            flags.add("overcurrent", lane, index, 3, value)
        elif value >= warn:
            flags.add("overcurrent", lane, index, 2, value)

    powered = [value for value in volt if value == value and value >= THRESHOLDS["volt_powered"]]
    reference = _median(powered) if len(powered) >= 20 else None
    sags = 0
    if reference is not None:
        limit = reference * THRESHOLDS["volt_sag_ratio"]
        off = reference * THRESHOLDS["volt_off_ratio"]
        max_sec = THRESHOLDS["volt_sag_max_sec"]
        offsets = columns.t_off
        # A sag is a short dip from a powered rail that comes back to the
        # powered level. A rail that decays to off is a power-down (the
        # capacitors discharging), a long dip is the supply switched off for
        # a while, and a ramp from off is a power-up; none of those are
        # flagged. Candidate rows are held until we know which it was.
        was_powered = False
        pending: list[int] = []
        for index in range(columns.n):
            value = volt[index]
            if value != value:
                continue
            if value >= limit:
                if pending and offsets[pending[-1]] - offsets[pending[0]] <= max_sec:
                    for held in pending:
                        flags.add("undervolt", lane, held, 2, volt[held])
                    sags += len(pending)
                pending = []
                was_powered = True
            elif value <= off:
                pending = []
                was_powered = False
            elif was_powered:
                pending.append(index)

    amps.sort()
    watts = [value for value in watt if value == value]
    return {
        "amp_mean": (sum(amps) / len(amps)) if amps else None,
        "amp_p99": _percentile(amps, 0.99),
        "amp_max": amps[-1] if amps else None,
        "amp_max_index": max_amp_index,
        "volt_powered_median": reference,
        "volt_powered_min": min(powered) if powered else None,
        "volt_sag_samples": sags,
        "watt_max": max(watts) if watts else None,
    }


def _detect_link_and_timing(columns: TakeColumns, flags: _Flags) -> float:
    """Dropped cycles, receive gaps, overruns and jitter. Returns the period."""
    count = columns.n
    seq = columns.seq
    offsets = columns.t_off
    periods = [value for value in columns.sys["period_us"] if value == value and value > 0]
    target = _median(periods) if periods else None
    target = target or DEFAULT_TARGET_PERIOD_US
    rx_warn = THRESHOLDS["rx_gap_warn_sec"]
    rx_crit = THRESHOLDS["rx_gap_crit_sec"]
    jitter_limit = THRESHOLDS["jitter_warn_us"]
    loop = columns.sys["loop_us"]
    jitter = columns.sys["jitter_us"]
    overrun = columns.overrun

    for index in range(count):
        if index > 0:
            before = seq[index - 1]
            after = seq[index]
            if before >= 0 and after >= 0:
                lost = after - before - 1
                if lost > 0:
                    flags.add("seq_drop", "link", index, 2, float(lost))
                elif after <= before:
                    flags.add("seq_reset", "link", index, 3, float(after - before))
            gap = offsets[index] - offsets[index - 1]
            if gap >= rx_crit:
                flags.add("rx_gap", "link", index, 3, gap)
            elif gap >= rx_warn:
                flags.add("rx_gap", "link", index, 2, gap)
        if overrun[index] == 1:
            spent = loop[index]
            severe = spent == spent and spent >= 2 * target
            flags.add("overrun", "timing", index, 3 if severe else 2, spent)
        drift = jitter[index]
        if drift == drift and abs(drift) >= jitter_limit:
            flags.add("jitter", "timing", index, 2, drift)
    return target


def _detect_i2c(columns: TakeColumns, flags: _Flags) -> dict[str, Any]:
    """Growth of the summed I2C failure counter.

    Severity is the number of new failures inside the last second, so a
    steady trickle and a burst read differently.
    """
    delta = columns.values("sys.i2c_delta")
    offsets = columns.t_off
    crit = THRESHOLDS["i2c_crit_per_sec"]
    window: deque[tuple[float, float]] = deque()
    in_window = 0.0
    peak_rate = 0.0
    for index in range(columns.n):
        value = delta[index]
        if value != value or value <= 0:
            continue
        now = offsets[index]
        window.append((now, value))
        in_window += value
        while window and now - window[0][0] > 1.0:
            in_window -= window.popleft()[1]
        peak_rate = max(peak_rate, in_window)
        flags.add("i2c", "i2c", index, 3 if in_window >= crit else 2, value)
    counters = [value for value in columns.i2c_err if value >= 0]
    return {
        "start": counters[0] if counters else None,
        "end": counters[-1] if counters else None,
        "max_per_sec": peak_rate,
    }


def _detect_servo(columns: TakeColumns, flags: _Flags) -> None:
    """Servo driver not answering. Before its first answer it is "no data"."""
    seen = False
    for index, value in enumerate(columns.servo_ok):
        if value == 1:
            seen = True
        elif value == 0:
            if seen:
                flags.add("servo_lost", "servo", index, 3)
            else:
                flags.add("nodata", "servo", index, 1)


def _detect_foot(columns: TakeColumns, flags: _Flags, foot: str) -> None:
    """Foot slave dropouts, missing fitted corners and over-range corners.

    Mask bits follow schema order: bit 0 top_left, 1 top_right,
    2 bottom_right, 3 bottom_left.
    """
    target = columns.feet[foot]
    ok = target["ok"]
    mask = target["mask"]
    corners = [target[short] for short, _ in CORNERS]
    rated = THRESHOLDS["foot_rated_kg"]
    seen = False
    for index in range(columns.n):
        state = ok[index]
        if state == 1:
            seen = True
            fitted = mask[index]
            for bit, values in enumerate(corners):
                value = values[index]
                if value != value:
                    if fitted >= 0 and fitted & (1 << bit):
                        flags.add("corner_missing", foot, index, 2, float(bit))
                elif value >= rated:
                    flags.add("foot_saturated", foot, index, 2, value)
        elif state == 0:
            if seen:
                flags.add("foot_lost", foot, index, 2)
            else:
                flags.add("nodata", foot, index, 1)


def _detect_events(columns: TakeColumns, flags: _Flags, events: list[dict[str, Any]]) -> None:
    if not columns.n:
        return
    for event in events:
        if event["level"] != "error" or event["offset"] is None:
            continue
        index = _nearest_index(columns.t_off, event["offset"])
        flags.add("event_error", "events", index, 3)


def _detect_stop(columns: TakeColumns, flags: _Flags, meta: LabTakeMeta) -> dict[str, Any] | None:
    """A recording that ended on an error is a finding at its last row."""
    reason = (meta.stop_reason or "").strip()
    if not reason or reason in _NORMAL_STOPS or meta.recording or not columns.n:
        return None
    severity = 3 if _CRIT_STOP_RE.search(reason) else 2
    last = columns.n - 1
    flags.sev["events"][last] = max(flags.sev["events"][last], severity)
    flags.kind["events"][last] = KIND_INDEX["abnormal_stop"]
    return _single_finding(
        columns,
        kind="abnormal_stop",
        lane="events",
        severity=severity,
        start=last,
        end=last,
        sample_count=1,
        peak_index=last,
        peak_value=math.nan,
        detail={"stop_reason": reason},
    )


def _load_events(take_dir: Path, columns: TakeColumns) -> tuple[list[dict[str, Any]], int]:
    """Event screen lines on the take time axis, with level and joint."""
    events: list[dict[str, Any]] = []
    total = 0
    for line in iter_event_lines(take_dir):
        total += 1
        if len(events) >= MAX_EVENTS:
            continue
        stamp, text = split_event(line)
        parsed = parse_iso(stamp) if stamp else None
        offset = None
        if parsed is not None and columns.n:
            try:
                offset = round(parsed.timestamp() - columns.t0, 3)
            except (OverflowError, OSError, ValueError):
                offset = None
        joint_match = _EVENT_JOINT_RE.search(text)
        joint = int(joint_match.group(1)) if joint_match else None
        events.append(
            {
                "offset": offset,
                "text": text,
                "level": _event_level(text),
                "joint": joint if joint is not None and 0 <= joint < JOINT_COUNT else None,
            }
        )
    return events, total


def _event_level(text: str) -> str:
    if _EVENT_ERROR_RE.search(text):
        return "error"
    if _EVENT_RECOVER_RE.search(text):
        return "info"
    if _EVENT_WARN_RE.search(text):
        return "warn"
    return "info"


def _load_commands(take_dir: Path, columns: TakeColumns) -> tuple[list[dict[str, Any]], int]:
    """PC to board commands (CMD, OUT, MODE, PING ...) on the take time axis."""
    folder = take_dir / "commands"
    if not folder.is_dir() or not columns.n:
        return [], 0
    commands: list[dict[str, Any]] = []
    total = 0
    for row in _iter_jsonl(part_paths(folder, ".jsonl")):
        stamp = row.get("t")
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
            continue
        total += 1
        if len(commands) >= MAX_COMMANDS:
            continue
        entry: dict[str, Any] = {"offset": round(float(stamp) - columns.t0, 4), "text": str(row.get("text", ""))}
        # enable / vx ride on POLICY rows (core_take_v2). Older commands omit them.
        for key in ("ch", "deg", "on", "mode", "enable", "vx"):
            value = row.get(key)
            if isinstance(value, (bool, int, float, str)):
                entry[key] = value
        commands.append(entry)
    return commands, total


def _iter_jsonl(paths: list[Path]) -> Iterator[dict[str, Any]]:
    for path in paths:
        try:
            handle = path.open("rb")
        except OSError:
            continue
        with handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except ValueError:
                    continue
                if isinstance(payload, dict):
                    yield payload


def _out_spans(columns: TakeColumns, joint: int) -> list[list[float]]:
    """[start, end] offsets where this axis's PWM output was enabled."""
    out = columns.values(f"j{joint}.out")
    offsets = columns.t_off
    spans: list[list[float]] = []
    start: float | None = None
    for index in range(columns.n):
        if out[index] == 1.0:
            if start is None:
                start = offsets[index]
        elif start is not None:
            spans.append([round(start, 3), round(offsets[index], 3)])
            start = None
            if len(spans) >= MAX_INTERVALS:
                break
    if start is not None and len(spans) < MAX_INTERVALS:
        spans.append([round(start, 3), round(columns.duration, 3)])
    return spans


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


def _badness(kind: str, value: float) -> float:
    """Larger is worse. Undervolt is worst at the lowest voltage."""
    if value != value:
        return -math.inf
    if kind == "undervolt":
        return -value
    return abs(value)


def _build_findings(
    columns: TakeColumns,
    flags: _Flags,
    extras: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Runs of flags become findings: one group per (kind, lane) with intervals."""
    offsets = columns.t_off
    merge_gap = THRESHOLDS["merge_gap_sec"]
    findings: list[dict[str, Any]] = []
    for (kind, lane), items in flags.groups.items():
        items.sort(key=lambda item: item[0])
        intervals: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for index, severity, value in items:
            if current is not None and offsets[index] - offsets[current["end_index"]] <= merge_gap:
                current["end_index"] = index
                current["count"] += 1
                current["severity"] = max(current["severity"], severity)
                if _badness(kind, value) > _badness(kind, current["peak_value"]):
                    current["peak_value"] = value
                    current["peak_index"] = index
                continue
            if current is not None:
                intervals.append(current)
            current = {
                "start_index": index,
                "end_index": index,
                "count": 1,
                "severity": severity,
                "peak_value": value,
                "peak_index": index,
            }
        if current is not None:
            intervals.append(current)

        worst = max(intervals, key=lambda item: (_badness(kind, item["peak_value"]), item["count"]))
        finding = {
            "id": f"{kind}:{lane}",
            "kind": kind,
            "lane": lane,
            "joint": _lane_joint(lane),
            "severity": max(item["severity"] for item in intervals),
            "sample_count": len(items),
            "ratio": len(items) / columns.n if columns.n else 0.0,
            "first_offset": offsets[items[0][0]],
            "last_offset": offsets[items[-1][0]],
            "peak_value": _r(worst["peak_value"]),
            "peak_index": worst["peak_index"],
            "peak_offset": offsets[worst["peak_index"]],
            "interval_count": len(intervals),
            "periodic_sec": _periodicity([offsets[item["start_index"]] for item in intervals]),
            "detail": _finding_detail(kind, lane, items, intervals, flags, offsets, events),
            "intervals": [_interval_out(item, offsets) for item in intervals[:MAX_INTERVALS]],
        }
        findings.append(finding)

    findings.extend(extras)
    # Worst first, then by how much of the take it affects: a joint that is
    # blind for minutes outranks a single late row at power-up.
    findings.sort(key=lambda item: (-item["severity"], -item["sample_count"], item["first_offset"], item["lane"]))
    return findings


def _single_finding(
    columns: TakeColumns,
    *,
    kind: str,
    lane: str,
    severity: int,
    start: int,
    end: int,
    sample_count: int,
    peak_index: int,
    peak_value: float,
    detail: dict[str, Any],
) -> dict[str, Any]:
    """A finding that is one judgement over a span, not a run of row flags."""
    offsets = columns.t_off
    interval = {
        "start_index": start,
        "end_index": end,
        "count": sample_count,
        "severity": severity,
        "peak_value": peak_value,
        "peak_index": peak_index,
    }
    return {
        "id": f"{kind}:{lane}",
        "kind": kind,
        "lane": lane,
        "joint": _lane_joint(lane),
        "severity": severity,
        "sample_count": sample_count,
        "ratio": sample_count / columns.n if columns.n else 0.0,
        "first_offset": offsets[start],
        "last_offset": offsets[end],
        "peak_value": _r(peak_value),
        "peak_index": peak_index,
        "peak_offset": offsets[peak_index],
        "interval_count": 1,
        "periodic_sec": None,
        "detail": {key: (_r(value) if isinstance(value, float) else value) for key, value in detail.items()},
        "intervals": [_interval_out(interval, offsets)],
    }


def _interval_out(item: dict[str, Any], offsets: array) -> dict[str, Any]:
    return {
        "start_index": item["start_index"],
        "end_index": item["end_index"],
        "start_offset": offsets[item["start_index"]],
        "end_offset": offsets[item["end_index"]],
        "count": item["count"],
        "severity": item["severity"],
        "peak_value": _r(item["peak_value"]),
        "peak_index": item["peak_index"],
        "peak_offset": offsets[item["peak_index"]],
    }


def _finding_detail(
    kind: str,
    lane: str,
    items: list[tuple[int, int, float]],
    intervals: list[dict[str, Any]],
    flags: _Flags,
    offsets: array,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extra facts per kind, plus which joints were also unhealthy meanwhile."""
    detail: dict[str, Any] = {}
    if kind in ("dropout", "magnet"):
        codes = Counter(int(value) for _, _, value in items if value == value)
        detail["mag"] = {str(code): number for code, number in sorted(codes.items())}
    elif kind == "seq_drop":
        detail["dropped_total"] = int(sum(value for _, _, value in items if value == value))
    elif kind == "i2c":
        detail["i2c_total"] = int(sum(value for _, _, value in items if value == value))
    elif kind == "corner_missing":
        corners = Counter(CORNERS[int(value)][0] for _, _, value in items if value == value)
        detail["corners"] = dict(corners)
    elif kind == "event_error":
        start = offsets[items[0][0]] - 0.5
        end = offsets[items[-1][0]] + 0.5
        detail["texts"] = [
            event["text"]
            for event in events
            if event["level"] == "error" and event["offset"] is not None and start <= event["offset"] <= end
        ][:8]

    if lane in SYSTEM_LANES or lane == "policy":
        related = _related_joints(intervals, flags)
        if related:
            detail["related"] = related
        mentioned = _mentioned_joints(intervals, offsets, events)
        if mentioned:
            detail["mentioned"] = mentioned
    return detail


def _related_joints(intervals: list[dict[str, Any]], flags: _Flags) -> list[dict[str, Any]]:
    """Joints that were warn/crit for a large share of a system finding.

    This is the "what else went wrong at the same time" hint: an I2C burst
    that lines up with one joint's encoder dropout points at that joint.
    """
    covered = 0
    hits = [0] * JOINT_COUNT
    for item in intervals:
        start = item["start_index"]
        end = item["end_index"] + 1
        covered += end - start
        for joint in range(JOINT_COUNT):
            row = flags.sev[f"j{joint}"]
            hits[joint] += sum(1 for value in row[start:end] if value >= 2)
    if not covered:
        return []
    related = [
        {"joint": joint, "ratio": round(hits[joint] / covered, 3)}
        for joint in range(JOINT_COUNT)
        if hits[joint] / covered >= 0.3
    ]
    related.sort(key=lambda item: -item["ratio"])
    return related[:4]


def _mentioned_joints(
    intervals: list[dict[str, Any]],
    offsets: array,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Joints named in event lines during the finding (e.g. AS5600関節3)."""
    spans = [(offsets[item["start_index"]] - 1.0, offsets[item["end_index"]] + 1.0) for item in intervals]
    counts: Counter[int] = Counter()
    for event in events:
        joint = event["joint"]
        offset = event["offset"]
        if joint is None or offset is None:
            continue
        if any(start <= offset <= end for start, end in spans):
            counts[joint] += 1
    return [{"joint": joint, "count": number} for joint, number in counts.most_common(4)]


def _periodicity(starts: list[float]) -> float | None:
    """Median spacing when intervals repeat like a clock (MAD within 10%)."""
    if len(starts) < 6:
        return None
    gaps = sorted(b - a for a, b in zip(starts, starts[1:]))
    median = _percentile(gaps, 0.5)
    if not median or median <= 0:
        return None
    spread = _median([abs(gap - median) for gap in gaps])
    if spread is None or spread > 0.1 * median:
        return None
    return round(median, 3)


def _lane_joint(lane: str) -> int | None:
    if lane.startswith("j") and lane[1:].isdigit():
        return int(lane[1:])
    return None


# ---------------------------------------------------------------------------
# Health map and stats
# ---------------------------------------------------------------------------


def _health(columns: TakeColumns, flags: _Flags, buckets: int) -> dict[str, Any]:
    """Lanes x equal-time buckets: worst severity, its kind and the bad share.

    Equal-time buckets keep the map aligned with the time axis of the plots.
    ``samples`` is the row count per bucket; 0 means nothing was received.
    """
    count = columns.n
    if count == 0:
        return {"buckets": 0, "bucket_sec": 0.0, "samples": [], "lanes": [], "overview": {}}
    offsets = columns.t_off
    width = max(columns.duration, 1e-6) / buckets
    bucket_of = array("i", (min(buckets - 1, int(offset / width)) for offset in offsets))
    samples = [0] * buckets
    for bucket in bucket_of:
        samples[bucket] += 1

    lanes: list[dict[str, Any]] = []
    for lane in flags.lanes:
        sev_row = flags.sev[lane]
        kind_row = flags.kind[lane]
        sev = [0] * buckets
        kind = [0] * buckets
        bad = [0] * buckets
        for index in range(count):
            level = sev_row[index]
            if not level:
                continue
            bucket = bucket_of[index]
            if level > sev[bucket]:
                sev[bucket] = level
                kind[bucket] = kind_row[index]
            if level >= 2:
                bad[bucket] += 1
        entry: dict[str, Any] = {
            "id": lane,
            "joint": _lane_joint(lane),
            "sev": sev,
            "kind": kind,
            "ratio": [round(bad[b] / samples[b], 3) if samples[b] else 0.0 for b in range(buckets)],
        }
        joint = _lane_joint(lane)
        if joint is not None:
            entry["out"] = _bucket_mean(columns.values(f"j{joint}.out"), bucket_of, buckets, digits=2)
        lanes.append(entry)

    # Context sparklines: total current and worst driven tracking error.
    amp_total = array("d", [0.0] * count)
    err_worst = array("d", [math.nan] * count)
    for joint in range(JOINT_COUNT):
        amp = columns.joint_float["amp"][joint]
        err = columns.values(f"j{joint}.err")
        out = columns.values(f"j{joint}.out")
        for index in range(count):
            value = amp[index]
            if value == value and value > 0:
                amp_total[index] += value
            if out[index] == 1.0:
                deviation = abs(err[index])
                if deviation == deviation and not (deviation <= err_worst[index]):
                    err_worst[index] = deviation
    return {
        "buckets": buckets,
        "bucket_sec": width,
        "samples": samples,
        "lanes": lanes,
        "overview": {
            "amp_total_max": _bucket_max(amp_total, bucket_of, buckets),
            "err_driven_max": _bucket_max(err_worst, bucket_of, buckets),
        },
    }


def _bucket_max(values: array, bucket_of: array, buckets: int) -> list[float | None]:
    out: list[float | None] = [None] * buckets
    for index, value in enumerate(values):
        if value != value:
            continue
        bucket = bucket_of[index]
        current = out[bucket]
        if current is None or value > current:
            out[bucket] = value
    return [_r(value) if value is not None else None for value in out]


def _bucket_mean(values: array, bucket_of: array, buckets: int, *, digits: int) -> list[float | None]:
    total = [0.0] * buckets
    seen = [0] * buckets
    for index, value in enumerate(values):
        if value != value:
            continue
        bucket = bucket_of[index]
        total[bucket] += value
        seen[bucket] += 1
    return [round(total[b] / seen[b], digits) if seen[b] else None for b in range(buckets)]


def _joint_stats(
    columns: TakeColumns,
    per_joint: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stats: list[dict[str, Any]] = []
    for joint in range(JOINT_COUNT):
        info = per_joint[joint]
        presence = info["presence"]
        agc = sorted(value for value in columns.joint_int["agc"][joint] if 0 <= value < 255)
        own = [item for item in findings if item["joint"] == joint and item["severity"] >= 2]
        stats.append(
            {
                "index": joint,
                "name": JOINT_NAMES[joint],
                "online_ratio": info["online_ratio"],
                "as_ok_ratio": (presence["as_ok"] / presence["online"]) if presence["online"] else None,
                "dropout_samples": presence["dropout"],
                "mag_counts": presence["mag_counts"],
                "agc_min": agc[0] if agc else None,
                "agc_median": _percentile(agc, 0.5),
                "agc_max": agc[-1] if agc else None,
                "out_ratio": info["out_ratio"],
                "jump_count": info["jumps"],
                "tracking": _clean_dict(info["tracking"]),
                "power": _clean_dict(info["power"]),
                "crit": sum(1 for item in own if item["severity"] >= 3),
                "warn": sum(1 for item in own if item["severity"] == 2),
            }
        )
    return stats


def _system_stats(
    columns: TakeColumns,
    flags: _Flags,
    findings: list[dict[str, Any]],
    target_period: float,
    i2c: dict[str, Any],
) -> dict[str, Any]:
    count = columns.n
    duration = columns.duration
    period = sorted(value for value in columns.sys["period_us"] if value == value)
    loop = sorted(value for value in columns.sys["loop_us"] if value == value)
    sense = sorted(value for value in columns.sys["sense_us"] if value == value)
    jitter = sorted(abs(value) for value in columns.sys["jitter_us"] if value == value)
    if getattr(columns, "sim_clock", False):
        # Chart axis is the simulator step, so the interval card must not
        # report the PC's irregular wall-clock gaps.
        offsets = columns.t_off
        dt = sorted((offsets[index] - offsets[index - 1]) * 1000.0 for index in range(1, len(offsets)))
    else:
        dt = sorted(value for value in columns.values("sys.dt_ms") if value == value)
    drops = flags.groups.get(("seq_drop", "link"), [])
    gaps = flags.groups.get(("rx_gap", "link"), [])
    resets = flags.groups.get(("seq_reset", "link"), [])
    drop_finding = next((item for item in findings if item["id"] == "seq_drop:link"), None)
    i2c_delta = None
    if i2c["start"] is not None and i2c["end"] is not None:
        i2c_delta = i2c["end"] - i2c["start"]
    return _clean_dict(
        {
            "rate_hz": (count - 1) / duration if duration > 0 else None,
            "target_period_us": target_period,
            "period_mean_us": (sum(period) / len(period)) if period else None,
            "period_std_us": _std(period),
            "period_p99_us": _percentile(period, 0.99),
            "period_max_us": period[-1] if period else None,
            "loop_p99_us": _percentile(loop, 0.99),
            "loop_max_us": loop[-1] if loop else None,
            "sense_median_us": _percentile(sense, 0.5),
            "sense_max_us": sense[-1] if sense else None,
            "jitter_abs_p99_us": _percentile(jitter, 0.99),
            "overrun_count": sum(1 for value in columns.overrun if value == 1),
            "seq_drop_events": len(drops),
            "seq_dropped_total": int(sum(value for _, _, value in drops if value == value)),
            "seq_drop_periodic_sec": drop_finding["periodic_sec"] if drop_finding else None,
            "seq_resets": len(resets),
            "rx_gap_count": len(gaps),
            "rx_gap_max_sec": max((value for _, _, value in gaps), default=None),
            "dt_median_ms": _percentile(dt, 0.5),
            "dt_p99_ms": _percentile(dt, 0.99),
            "dt_max_ms": dt[-1] if dt else None,
            "i2c_start": i2c["start"],
            "i2c_end": i2c["end"],
            "i2c_delta": i2c_delta,
            "i2c_max_per_sec": i2c["max_per_sec"],
            "servo_ok_ratio": _flag_ratio(columns.servo_ok),
            "foot_ok_ratio": _flag_ratio(columns.feet["foot"]["ok"]),
            "foot_left_ok_ratio": _flag_ratio(columns.feet["foot_left"]["ok"]),
            "modes": list(columns.mode_names),
        }
    )


def _describe_range(values: array, lo: int, hi: int, offsets: array) -> dict[str, Any]:
    """n, gaps, min/max with their index, mean, std, percentiles, first/last."""
    finite: list[tuple[float, int]] = [(values[index], index) for index in range(lo, hi) if values[index] == values[index]]
    missing = (hi - lo) - len(finite)
    if not finite:
        return {"n": 0, "missing": missing}
    ordered = sorted(value for value, _ in finite)
    low = min(finite, key=lambda item: item[0])
    high = max(finite, key=lambda item: item[0])
    mean = sum(ordered) / len(ordered)
    return _clean_dict(
        {
            "n": len(finite),
            "missing": missing,
            "min": low[0],
            "min_index": low[1],
            "min_offset": offsets[low[1]],
            "max": high[0],
            "max_index": high[1],
            "max_offset": offsets[high[1]],
            "mean": mean,
            "std": _std(ordered),
            "p05": _percentile(ordered, 0.05),
            "p50": _percentile(ordered, 0.5),
            "p95": _percentile(ordered, 0.95),
            "first": finite[0][0],
            "last": finite[-1][0],
            "delta": finite[-1][0] - finite[0][0],
        }
    )


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------


def _percentile(ordered: list[float], q: float) -> float | None:
    """Linear interpolation on an already sorted list."""
    if not ordered:
        return None
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return float(ordered[low])
    return float(ordered[low] + (ordered[high] - ordered[low]) * (pos - low))


def _median(values: list[float]) -> float | None:
    return _percentile(sorted(values), 0.5)


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _flag_ratio(flags: array) -> float | None:
    known = [value for value in flags if value >= 0]
    if not known:
        return None
    return sum(1 for value in known if value == 1) / len(known)


def _r(value: float | None) -> float | None:
    """JSON-safe rounding. NaN and infinities become null (a gap)."""
    if value is None or value != value or value in (math.inf, -math.inf):
        return None
    return round(float(value), 4)


def _clean_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace NaN/inf floats with None so the response stays valid JSON."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, float) and not math.isfinite(value):
            out[key] = None
        else:
            out[key] = value
    return out
