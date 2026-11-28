# -*- coding: utf-8 -*-
"""Columnar, cached view of one take's sensor rows.

The jsonl parts on the NAS stay the record. Parsing ~40 MB of JSON on every
chart request would be slow, so each take is parsed once into compact typed
arrays (``array.array``) and kept in a small LRU keyed by the part files'
size and mtime. A take that is still recording gets re-parsed as soon as a
new part lands, because the signature changes.

Missing values never become fake zeros:

* float channels hold NaN
* flag channels hold -1 (unknown), 0 (false) or 1 (true)
* integer channels hold -1

Every row remembers its part file, byte offset and line number so the
inspector can show the exact original line from disk.

Channel ids used by the API (all values come back as floats, NaN = gap):

* ``j<N>.<field>``  per logical axis N (0-9). Stored fields plus derived
  ``err`` (corr - cmd) and ``out`` (bit N of out_mask).
* ``sys.<field>``   firmware timing, counters and derived link health
  (``i2c_delta``, ``seq_gap``, ``dt_ms``).
* ``foot.<field>`` / ``foot_left.<field>``  foot slave, including corner
  forces (``tl`` ``tr`` ``br`` ``bl``) and derived centre of pressure
  (``cop_x`` ``cop_y``, -1..1).
* ``pad.<field>``  gamepad folded onto the sensor clock. Sticks and heel
  targets keep the last value in each sensor interval. ``l_accepted`` and
  ``r_accepted`` are 1 when any pad row in that interval advanced the heel,
  not a count of those rows. Before the first pad row every pad channel
  is NaN. Rows after the last sensor sample are counted in the summary
  and omitted from the chart.
"""

from __future__ import annotations

import json
import math
import re
import threading
from array import array
from bisect import bisect_right
from collections import OrderedDict
from pathlib import Path
from typing import Any

JOINT_COUNT = 10
NAN = float("nan")

# Per-joint arrays in each sensor row, split by how they are stored.
JOINT_FLOAT_FIELDS: tuple[str, ...] = ("cmd", "raw", "unwrap", "corr", "volt", "amp", "watt")
JOINT_FLAG_FIELDS: tuple[str, ...] = ("as_ok", "ina_ok", "map_ok")
JOINT_INT_FIELDS: tuple[str, ...] = ("mag", "agc")
# "sev" is the detector verdict per row. It is resolved by lab_analysis,
# which owns the detectors; TakeColumns itself cannot produce it.
# corr_rad / cmd_rad are degrees rewritten as radians from upright, so they
# share an axis with the policy's obs and cmd_rad. v1 takes can read them too.
JOINT_DERIVED_FIELDS: tuple[str, ...] = ("err", "out", "sev", "corr_rad", "cmd_rad")

# Firmware timing fields, all in microseconds.
SYS_FLOAT_FIELDS: tuple[str, ...] = ("period_us", "loop_us", "sense_us", "jitter_us")
SYS_OTHER_FIELDS: tuple[str, ...] = (
    "overrun",
    "servo_ok",
    "i2c_err",
    "i2c_delta",
    "out_mask",
    "seq",
    "seq_gap",
    "dt_ms",
)

FEET: tuple[str, ...] = ("foot", "foot_left")
# Short corner keys used in channel ids, paired with the schema key.
CORNERS: tuple[tuple[str, str], ...] = (
    ("tl", "top_left"),
    ("tr", "top_right"),
    ("br", "bottom_right"),
    ("bl", "bottom_left"),
)
FOOT_FIELDS: tuple[str, ...] = ("ok", "seq", "mask", "force_kg", "tl", "tr", "br", "bl", "cop_x", "cop_y")

# AS5600 STATUS / AGC use 255 for "not read this cycle". That is a gap,
# not a reading, so channel values turn it into NaN.
SKIP_CODE = 255

# Below this total load the centre of pressure is noise, so it stays a gap.
COP_MIN_TOTAL_KG = 0.02

# Gamepad jsonl is a second clock (~50 Hz). Channels below are one value
# per sensor row, so the existing window / stats / CSV path can plot them.
# Floats and hold-flags repeat the last sample in (previous t, this t].
# Pulse flags are the max in that same interval (0 once the pad has started).
PAD_FLOAT_FIELDS: tuple[str, ...] = (
    "l_forward",
    "l_lateral",
    "l_vertical",
    "l_raw_forward",
    "l_raw_lateral",
    "l_trigger",
    "l_heel_x",
    "l_heel_y",
    "l_heel_z",
    "r_forward",
    "r_lateral",
    "r_vertical",
    "r_raw_forward",
    "r_raw_lateral",
    "r_trigger",
    "r_heel_x",
    "r_heel_y",
    "r_heel_z",
)
# States: keep the last sample. A gap before the pad starts stays NaN.
PAD_HOLD_FIELDS: tuple[str, ...] = (
    "connected",
    "homing",
    "l_bumper",
    "r_bumper",
    "l_floor",
    "r_floor",
)
# One step of inverse kinematics. Several pad rows often share one sensor
# row, so this is "advanced during this interval", not the native row count.
PAD_PULSE_FIELDS: tuple[str, ...] = ("l_accepted", "r_accepted")
PAD_FIELDS: tuple[str, ...] = PAD_FLOAT_FIELDS + PAD_HOLD_FIELDS + PAD_PULSE_FIELDS

# Policy channels. ``p<N>`` is a logical axis (the screen order), already
# remapped out of the policy file's left/right order. The values are gathered
# onto sensor time; see lab_policy.
POLICY_JOINT_FIELDS: tuple[str, ...] = (
    "obs",
    "action",
    "action_rad",
    "cmd_rad",
    "clip",
    "flag",
    "age",
    "prev",
)
IMU_FIELDS: tuple[str, ...] = ("gx", "gy", "gz", "wx", "wy", "wz", "gmag")
POL_FIELDS: tuple[str, ...] = (
    "reason",
    "safety",
    "bearing",
    "dist",
    "overrun",
    "period_us",
    "sense_us",
    "policy_us",
    "dt_ms",
    "phase_sin",
    "phase_cos",
    "vx",
    "yaw",
    "age_imu",
    "age_foot",
)
PF_FIELDS: tuple[str, ...] = ("l_tl", "l_tr", "l_bl", "l_br", "r_tl", "r_tr", "r_bl", "r_br")
# Processed stick axes. raw_* jitters around 0 at rest and must not count.
_PAD_STICK_AXES: tuple[str, ...] = (
    "l_forward",
    "l_lateral",
    "l_vertical",
    "r_forward",
    "r_lateral",
    "r_vertical",
)

# j/p take one digit: axes are 0-9. imu/pol/pf are the policy-wide series.
_CHANNEL_RE = re.compile(
    r"^(?:j(\d)|p(\d)|(sys)|(foot|foot_left)|(pad)|(imu)|(pol)|(pf))\.([a-z0-9_]+)$"
)
_PART_RE = re.compile(r"part-(\d+)")

# Parsed takes kept in memory. Three keeps a comparison session snappy
# while bounding memory (one 15 minute take is roughly 20 MB of float64
# arrays). float64 is deliberate: the table shows the recorded numbers,
# and float32 would round them in the 5th-6th digit.
_CACHE_MAX = 3
_CACHE: "OrderedDict[str, tuple[tuple[Any, ...], TakeColumns]]" = OrderedDict()
_CACHE_LOCK = threading.Lock()


class ChannelError(ValueError):
    """Raised for a channel id that does not exist."""


def parse_channel(channel: str) -> tuple[str, int | None, str]:
    """Split ``j3.corr`` into (scope, joint, field). Raises ChannelError.

    Policy scopes (``p``, ``imu``, ``pol``, ``pf``) are accepted even when
    the take has no policy file. Those channels then come back as gaps,
    so a v1 take does not 400 on a v2 chart request.
    """
    match = _CHANNEL_RE.match(channel)
    if not match:
        raise ChannelError(channel)
    joint_text, policy_text, sys_scope, foot_scope, pad_scope, imu_scope, pol_scope, pf_scope, field = match.groups()
    if joint_text is not None:
        joint = int(joint_text)
        allowed = JOINT_FLOAT_FIELDS + JOINT_FLAG_FIELDS + JOINT_INT_FIELDS + JOINT_DERIVED_FIELDS
        if joint >= JOINT_COUNT or field not in allowed:
            raise ChannelError(channel)
        return "joint", joint, field
    if policy_text is not None:
        joint = int(policy_text)
        if joint >= JOINT_COUNT or field not in POLICY_JOINT_FIELDS:
            raise ChannelError(channel)
        return "p", joint, field
    if sys_scope is not None:
        if field not in SYS_FLOAT_FIELDS + SYS_OTHER_FIELDS:
            raise ChannelError(channel)
        return "sys", None, field
    if pad_scope is not None:
        if field not in PAD_FIELDS:
            raise ChannelError(channel)
        return "pad", None, field
    if imu_scope is not None:
        if field not in IMU_FIELDS:
            raise ChannelError(channel)
        return "imu", None, field
    if pol_scope is not None:
        if field not in POL_FIELDS:
            raise ChannelError(channel)
        return "pol", None, field
    if pf_scope is not None:
        if field not in PF_FIELDS:
            raise ChannelError(channel)
        return "pf", None, field
    if field not in FOOT_FIELDS:
        raise ChannelError(channel)
    return str(foot_scope), None, field


def all_channels(include_pad: bool = False, include_policy: bool = False) -> list[str]:
    """Every channel id in a stable order. Used as the CSV export default.

    Pad and policy columns are included only when that take recorded them,
    so older takes do not grow a block of empty cells.
    """
    channels = [f"sys.{name}" for name in SYS_FLOAT_FIELDS + SYS_OTHER_FIELDS]
    joint_fields = (
        "sev",
        "cmd",
        "raw",
        "unwrap",
        "corr",
        "err",
        "as_ok",
        "mag",
        "agc",
        "map_ok",
        "volt",
        "amp",
        "watt",
        "ina_ok",
        "out",
    )
    for joint in range(JOINT_COUNT):
        channels.extend(f"j{joint}.{field}" for field in joint_fields)
    for foot in FEET:
        channels.extend(f"{foot}.{field}" for field in FOOT_FIELDS)
    if include_pad:
        channels.extend(f"pad.{field}" for field in PAD_FIELDS)
    if include_policy:
        # Sensor angles on the policy's radian-from-upright axis, then the
        # policy file itself. p<N> is already in logical-axis order.
        for joint in range(JOINT_COUNT):
            channels.append(f"j{joint}.corr_rad")
            channels.append(f"j{joint}.cmd_rad")
        for joint in range(JOINT_COUNT):
            channels.extend(f"p{joint}.{field}" for field in POLICY_JOINT_FIELDS)
        channels.extend(f"imu.{field}" for field in IMU_FIELDS)
        channels.extend(f"pol.{field}" for field in POL_FIELDS)
        channels.extend(f"pf.{field}" for field in PF_FIELDS)
    return channels


class _JointTable:
    """Per-joint values stored row-major (``row * 10 + joint``).

    Appending a whole row with one ``extend`` is several times faster than
    ten separate appends, which matters for a 40 MB take. Indexing by joint
    returns that joint's column, sliced once and cached.
    """

    def __init__(self, typecode: str) -> None:
        self.flat = array(typecode)
        self._columns: dict[int, array] = {}

    def __getitem__(self, joint: int) -> array:
        column = self._columns.get(joint)
        if column is None or len(column) * JOINT_COUNT != len(self.flat):
            column = self.flat[joint::JOINT_COUNT]
            self._columns[joint] = column
        return column


class TakeColumns:
    """Typed arrays for every sensor row of one take, in file order."""

    def __init__(self, paths: list[Path], sensors_dir: Path) -> None:
        self.paths = paths
        self.sensors_dir = sensors_dir
        # "sensors" for a real take. A playback with no sensor file rewrites
        # this to "policy" so the inspector cites policy/part-NNN.jsonl.
        self.part_prefix = "sensors"
        # True when the rows below were adopted from policy/ and the chart
        # axis is cumulative t_period_us, not wall-clock gaps.
        self.sim_clock = False
        self._sim_off: array | None = None
        # Row identity and where it came from on disk.
        self.t = array("d")
        self.seq = array("q")
        self.part = array("h")
        self.offset = array("q")
        self.line = array("i")
        # Firmware-wide fields.
        self.sys = {name: array("d") for name in SYS_FLOAT_FIELDS}
        self.overrun = array("b")
        self.servo_ok = array("b")
        self.i2c_err = array("q")
        self.out_mask = array("q")
        self.mode = array("b")
        self.mode_names: list[str] = []
        # Per logical axis. ``joint_float["cmd"][3]`` is axis 3's cmd column.
        self.joint_float = {name: _JointTable("d") for name in JOINT_FLOAT_FIELDS}
        self.joint_flag = {name: _JointTable("b") for name in JOINT_FLAG_FIELDS}
        self.joint_int = {name: _JointTable("h") for name in JOINT_INT_FIELDS}
        # Foot slaves. Forces are NaN whenever that sample's ok flag is not true.
        self.feet: dict[str, dict[str, array]] = {
            foot: {
                "ok": array("b"),
                "seq": array("q"),
                "mask": array("h"),
                "force_kg": array("d"),
                **{short: array("d") for short, _ in CORNERS},
            }
            for foot in FEET
        }
        self._values: dict[str, array] = {}
        self._t_off: array | None = None
        # Native gamepad rows (not aligned to sensors). Empty when the take
        # has no gamepad folder. Summary counts use these rows, not the
        # folded 0/1 series.
        self.pad_paths: list[Path] = []
        self.pad_t = array("d")
        self.pad_part = array("h")
        self.pad_offset = array("q")
        self.pad_line = array("i")
        self.pad_float = {name: array("d") for name in PAD_FLOAT_FIELDS}
        self.pad_flag = {name: array("b") for name in PAD_HOLD_FIELDS + PAD_PULSE_FIELDS}
        self.pad_stick_rows = 0
        self.pad_accepted_left = 0
        self.pad_accepted_right = 0
        self.pad_accepted_left_runs = 0
        self.pad_accepted_right_runs = 0
        self._pad_prev_acc_l = 0
        self._pad_prev_acc_r = 0
        # Sensor-aligned pad channels, built once on first read.
        self._pad_aligned: dict[str, array] | None = None
        # Analysis results keyed by their parameters. Dropped with the take.
        self.memo: dict[Any, Any] = {}
        self.memo_lock = threading.Lock()
        # Filled by lab_policy.attach_policy once the sensor rows exist.
        # upright is degrees per logical axis; policy channels are gaps until then.
        self.context: Any = None
        self.policy: Any = None
        self.upright: tuple[float, ...] = (135.0, 135.0, 0.0, 0.0, 135.0, 135.0, 135.0, 0.0, 0.0, 135.0)

    # ----- basic shape -------------------------------------------------

    @property
    def n(self) -> int:
        return len(self.t)

    @property
    def t0(self) -> float:
        """UNIX seconds of the first row. Every offset is relative to this."""
        return self.t[0] if self.t else 0.0

    @property
    def t_off(self) -> array:
        """Seconds since the first row, forced non-decreasing for bisect.

        PC receive time is monotonic in practice. Clamping only guards the
        index search against a clock step; it never reorders rows.
        """
        # Playback charts use simulator steps. Wall-clock t stays on self.t
        # so a policy channel still lands on its own row.
        if self._sim_off is not None:
            return self._sim_off
        if self._t_off is None:
            out = array("d")
            origin = self.t0
            last = 0.0
            for value in self.t:
                offset = value - origin
                if offset < last:
                    offset = last
                out.append(offset)
                last = offset
            self._t_off = out
        return self._t_off

    @property
    def duration(self) -> float:
        offsets = self.t_off
        return offsets[-1] if offsets else 0.0

    def location(self, index: int) -> tuple[str, int]:
        """(``sensors/part-NNN.jsonl``, 1-based line number) of a row."""
        path = self.paths[self.part[index]]
        return f"{self.part_prefix}/{path.name}", int(self.line[index])

    def read_line(self, index: int) -> str | None:
        """The exact text of one row as written in its part file."""
        path = self.paths[self.part[index]]
        try:
            with path.open("rb") as handle:
                handle.seek(self.offset[index])
                line = handle.readline()
        except OSError:
            return None
        return line.decode("utf-8", errors="replace").rstrip("\r\n")

    def read_row(self, index: int) -> dict[str, Any] | None:
        """The original JSON object for one row, read straight from disk."""
        line = self.read_line(index)
        if line is None:
            return None
        try:
            payload = json.loads(line)
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    # ----- channel values ----------------------------------------------

    def values(self, channel: str) -> array:
        """Float array for one channel id. NaN marks a gap. Cached."""
        cached = self._values.get(channel)
        if cached is not None:
            return cached
        scope, joint, field = parse_channel(channel)
        if scope == "joint":
            assert joint is not None
            out = self._joint_values(joint, field)
        elif scope == "sys":
            out = self._sys_values(field)
        elif scope == "pad":
            out = self._pad_values(field)
        elif scope == "p":
            assert joint is not None
            out = self._policy_channel(f"p{joint}.{field}")
        elif scope in ("imu", "pol", "pf"):
            out = self._policy_channel(channel)
        else:
            out = self._foot_values(scope, field)
        self._values[channel] = out
        return out

    def _joint_values(self, joint: int, field: str) -> array:
        if field in JOINT_FLOAT_FIELDS:
            return self.joint_float[field][joint]
        if field in JOINT_FLAG_FIELDS:
            return _flags_to_float(self.joint_flag[field][joint])
        if field in JOINT_INT_FIELDS:
            source = self.joint_int[field][joint]
            return array("d", (NAN if value < 0 or value == SKIP_CODE else float(value) for value in source))
        if field == "err":
            cmd = self.joint_float["cmd"][joint]
            corr = self.joint_float["corr"][joint]
            return array("d", (c - m if not (math.isnan(c) or math.isnan(m)) else NAN for c, m in zip(corr, cmd)))
        if field == "out":
            # Is the PWM for this axis enabled in this cycle.
            bit = 1 << joint
            return array("d", (NAN if mask < 0 else (1.0 if mask & bit else 0.0) for mask in self.out_mask))
        if field in ("corr_rad", "cmd_rad"):
            # Same origin as policy obs / cmd_rad: 0 is upright, radians.
            return self._upright_rad(joint, "corr" if field == "corr_rad" else "cmd")
        raise ChannelError(f"j{joint}.{field}")

    def _upright_rad(self, joint: int, field: str) -> array:
        source = self.joint_float[field][joint]
        upright = self.upright[joint] if joint < len(self.upright) else 0.0
        scale = math.pi / 180.0
        return array("d", (NAN if math.isnan(value) else (value - upright) * scale for value in source))

    def _policy_channel(self, name: str) -> array:
        """Policy series on this take's sensor clock. Gaps when policy/ is absent."""
        table = self.policy
        if table is None or table.n == 0:
            return array("d", [NAN] * self.n)
        return table.channel(self.t, name)

    def _sys_values(self, field: str) -> array:
        if field in SYS_FLOAT_FIELDS:
            return self.sys[field]
        if field == "overrun":
            return _flags_to_float(self.overrun)
        if field == "servo_ok":
            return _flags_to_float(self.servo_ok)
        if field == "i2c_err":
            return _ints_to_float(self.i2c_err)
        if field == "out_mask":
            return _ints_to_float(self.out_mask)
        if field == "seq":
            return _ints_to_float(self.seq)
        if field == "i2c_delta":
            # New I2C failures since the previous row. The counter is a running
            # total, so the per-row difference is what shows a burst.
            return _diff(self.i2c_err, lambda a, b: float(b - a))
        if field == "seq_gap":
            # Firmware cycles lost between two received rows. 0 is healthy,
            # negative means the counter went backwards (restart).
            return _diff(self.seq, lambda a, b: float(b - a - 1))
        # dt_ms: receive interval on the PC.
        out = array("d", [NAN] if self.t else [])
        for index in range(1, len(self.t)):
            out.append((self.t[index] - self.t[index - 1]) * 1000.0)
        return out

    def _foot_values(self, foot: str, field: str) -> array:
        target = self.feet[foot]
        if field == "ok":
            return _flags_to_float(target["ok"])
        if field in ("seq", "mask"):
            return _ints_to_float(target[field])
        if field in ("cop_x", "cop_y"):
            return self._cop(foot, field)
        return target[field]

    def _cop(self, foot: str, field: str) -> array:
        """Centre of pressure from the four corners, -1..1 on each axis.

        x is right minus left (top_right + bottom_right vs the left pair),
        y is top minus bottom. Needs all four corners and some load.
        """
        target = self.feet[foot]
        tl, tr, br, bl = target["tl"], target["tr"], target["br"], target["bl"]
        out = array("d")
        for a, b, c, d in zip(tl, tr, br, bl):
            total = a + b + c + d
            if math.isnan(total) or total < COP_MIN_TOTAL_KG:
                out.append(NAN)
            elif field == "cop_x":
                out.append(((b + c) - (a + d)) / total)
            else:
                out.append(((a + b) - (d + c)) / total)
        return out

    # ----- gamepad -----------------------------------------------------

    @property
    def pad_n(self) -> int:
        return len(self.pad_t)

    def gamepad_summary(self) -> dict[str, Any] | None:
        """Counts from the pad file itself. None when the take has no pad rows.

        ``accepted_*`` is the number of pad rows where that side advanced,
        and ``accepted_*_runs`` is how many contiguous bursts those rows
        form. The chart's 0/1 series is a different number: it collapses
        each burst onto the sensor rows it overlaps.
        """
        count = self.pad_n
        if count == 0:
            return None
        origin = self.t0
        span = self.pad_t[-1] - self.pad_t[0]
        rate = (count - 1) / span if count > 1 and span > 0 else None
        return {
            "samples": count,
            "rate_hz": rate,
            "start_offset": self.pad_t[0] - origin,
            "end_offset": self.pad_t[-1] - origin,
            "stick_rows": self.pad_stick_rows,
            "accepted_left": self.pad_accepted_left,
            "accepted_right": self.pad_accepted_right,
            "accepted_left_runs": self.pad_accepted_left_runs,
            "accepted_right_runs": self.pad_accepted_right_runs,
        }

    def pad_at(self, unix_t: float) -> dict[str, Any] | None:
        """Last gamepad row with ``t <= unix_t``. None before the pad starts.

        Sticks and heels on the chart hold this row. Accepted on the chart
        is the max over the whole sensor interval, so it can be 1 when this
        row itself is false. Rows after the last sensor sample are not
        returned, because no sensor time reaches them.
        """
        if not self.pad_t:
            return None
        index = bisect_right(self.pad_t, unix_t) - 1
        if index < 0:
            return None
        part_index = self.pad_part[index]
        path = self.pad_paths[part_index]
        raw_line: str | None = None
        try:
            with path.open("rb") as handle:
                handle.seek(self.pad_offset[index])
                raw_line = handle.readline().decode("utf-8", errors="replace").rstrip("\r\n")
        except OSError:
            raw_line = None
        row: dict[str, Any] | None = None
        if raw_line:
            try:
                parsed = json.loads(raw_line)
            except ValueError:
                parsed = None
            row = parsed if isinstance(parsed, dict) else None
        return {
            "t": float(self.pad_t[index]),
            "t_offset": float(self.pad_t[index] - self.t0),
            "part": f"gamepad/{path.name}",
            "line": int(self.pad_line[index]),
            "raw_line": raw_line,
            "row": row,
        }

    def _pad_values(self, field: str) -> array:
        aligned = self._align_pad()
        column = aligned.get(field)
        if column is None:
            raise ChannelError(f"pad.{field}")
        return column

    def _align_pad(self) -> dict[str, array]:
        """Fold pad rows onto sensor timestamps. Cached for the take.

        Interval of sensor row i is (t[i-1], t[i]]. Sticks, heels and
        state flags take the last pad row in the interval and then hold.
        Accepted takes the max, so a burst marks every sensor row it
        touches and does not stay on after it ends. Everything before
        the first pad row stays NaN, including a processed stick of 0.
        """
        cached = self._pad_aligned
        if cached is not None:
            return cached
        count = self.n
        floats = {name: array("d", [NAN] * count) for name in PAD_FLOAT_FIELDS}
        holds = {name: array("d", [NAN] * count) for name in PAD_HOLD_FIELDS}
        pulses = {name: array("d", [NAN] * count) for name in PAD_PULSE_FIELDS}
        aligned: dict[str, array] = {**floats, **holds, **pulses}
        self._pad_aligned = aligned
        pad_count = self.pad_n
        if count == 0 or pad_count == 0:
            return aligned

        hold_float: dict[str, float | None] = {name: None for name in PAD_FLOAT_FIELDS}
        hold_flag: dict[str, int | None] = {name: None for name in PAD_HOLD_FIELDS}
        started = False
        cursor = 0
        for index in range(count):
            lo = self.t[index - 1] if index else float("-inf")
            hi = self.t[index]
            while cursor < pad_count and self.pad_t[cursor] <= lo:
                cursor += 1
            last = -1
            pulse_best = {name: -1 for name in PAD_PULSE_FIELDS}
            scan = cursor
            while scan < pad_count and self.pad_t[scan] <= hi:
                last = scan
                for name in PAD_PULSE_FIELDS:
                    flag = self.pad_flag[name][scan]
                    if flag > pulse_best[name]:
                        pulse_best[name] = flag
                scan += 1
            cursor = scan
            if last >= 0:
                started = True
                for name in PAD_FLOAT_FIELDS:
                    value = self.pad_float[name][last]
                    if value == value:
                        hold_float[name] = value
                for name in PAD_HOLD_FIELDS:
                    flag = self.pad_flag[name][last]
                    if flag >= 0:
                        hold_flag[name] = flag
                for name in PAD_PULSE_FIELDS:
                    best = pulse_best[name]
                    pulses[name][index] = NAN if best < 0 else float(best)
            elif started:
                for name in PAD_PULSE_FIELDS:
                    pulses[name][index] = 0.0
            if not started:
                continue
            for name in PAD_FLOAT_FIELDS:
                value = hold_float[name]
                if value is not None:
                    floats[name][index] = value
            for name in PAD_HOLD_FIELDS:
                flag = hold_flag[name]
                if flag is not None:
                    holds[name][index] = float(flag)
        return aligned

    def append_pad(self, row: dict[str, Any], part_index: int, offset: int, line_no: int) -> None:
        """Copy one gamepad row. Counts runs on the native rows."""
        self.pad_t.append(float(row["t"]))
        self.pad_part.append(part_index)
        self.pad_offset.append(offset)
        self.pad_line.append(line_no)
        left = row.get("left") if isinstance(row.get("left"), dict) else {}
        right = row.get("right") if isinstance(row.get("right"), dict) else {}
        self._append_pad_stick("l", left)
        self._append_pad_stick("r", right)
        self._append_pad_heel("l", row.get("heel_left"))
        self._append_pad_heel("r", row.get("heel_right"))
        self.pad_flag["connected"].append(_flag(row.get("connected")))
        self.pad_flag["homing"].append(_flag(row.get("homing")))
        acc_l = _flag(row.get("accepted_left"))
        acc_r = _flag(row.get("accepted_right"))
        self.pad_flag["l_accepted"].append(acc_l)
        self.pad_flag["r_accepted"].append(acc_r)
        self.pad_flag["l_floor"].append(_flag(row.get("floor_hold_left")))
        self.pad_flag["r_floor"].append(_flag(row.get("floor_hold_right")))
        self._count_pad_row(acc_l, acc_r)

    def _append_pad_stick(self, side: str, stick: dict[str, Any]) -> None:
        for name in ("forward", "lateral", "vertical", "raw_forward", "raw_lateral", "trigger"):
            self.pad_float[f"{side}_{name}"].append(_num(stick.get(name)))
        self.pad_flag[f"{side}_bumper"].append(_flag(stick.get("bumper")))

    def _append_pad_heel(self, side: str, value: Any) -> None:
        """Heel target ``[x, y, z]`` in metres. A short or missing vector is a gap."""
        heel = value if isinstance(value, list) else []
        numbers = [_num(item) for item in heel[:3]]
        while len(numbers) < 3:
            numbers.append(NAN)
        for axis, item in zip("xyz", numbers):
            self.pad_float[f"{side}_heel_{axis}"].append(item)

    def _count_pad_row(self, acc_l: int, acc_r: int) -> None:
        """Native stick and accepted totals. Called after the row is stored."""
        active = False
        for name in _PAD_STICK_AXES:
            value = self.pad_float[name][-1]
            if value == value and value != 0.0:
                active = True
                break
        if active:
            self.pad_stick_rows += 1
        if acc_l == 1:
            self.pad_accepted_left += 1
            if self._pad_prev_acc_l != 1:
                self.pad_accepted_left_runs += 1
        if acc_r == 1:
            self.pad_accepted_right += 1
            if self._pad_prev_acc_r != 1:
                self.pad_accepted_right_runs += 1
        self._pad_prev_acc_l = acc_l
        self._pad_prev_acc_r = acc_r

    # ----- loading -----------------------------------------------------

    def append(self, row: dict[str, Any], part_index: int, offset: int, line_no: int) -> None:
        """Copy one parsed sensor row into the arrays."""
        self.t.append(float(row["t"]))
        self.part.append(part_index)
        self.offset.append(offset)
        self.line.append(line_no)
        self.seq.append(_int(row.get("seq")))
        for name in SYS_FLOAT_FIELDS:
            self.sys[name].append(_num(row.get(name)))
        self.overrun.append(_flag(row.get("overrun")))
        self.servo_ok.append(_flag(row.get("servo_ok")))
        self.i2c_err.append(_int(row.get("i2c_err")))
        self.out_mask.append(_int(row.get("out_mask")))
        self.mode.append(self._mode_index(row.get("mode")))

        # Hot loop: one extend per field per row. ``type(x) is float`` also
        # rejects bools (a JSON true is never a reading).
        for name in JOINT_FLOAT_FIELDS:
            self.joint_float[name].flat.extend(
                [
                    value if type(value) is float else (float(value) if type(value) is int else NAN)
                    for value in _fit(row.get(name))
                ]
            )
        for name in JOINT_FLAG_FIELDS:
            self.joint_flag[name].flat.extend(
                [1 if value is True else (0 if value is False else -1) for value in _fit(row.get(name))]
            )
        for name in JOINT_INT_FIELDS:
            self.joint_int[name].flat.extend(
                [
                    value if type(value) is int and 0 <= value <= 32767 else -1
                    for value in _fit(row.get(name))
                ]
            )

        for foot in FEET:
            self._append_foot(foot, row.get(foot))

    def _append_foot(self, foot: str, payload: Any) -> None:
        target = self.feet[foot]
        obj = payload if isinstance(payload, dict) else {}
        ok = _flag(obj.get("ok"))
        target["ok"].append(ok)
        target["seq"].append(_int(obj.get("seq")))
        target["mask"].append(_small(obj.get("mask")))
        # The file may store 0 kg while ok is false. That is a gap, not 0 kg.
        valid = ok == 1
        target["force_kg"].append(_num(obj.get("force_kg")) if valid else NAN)
        corners = obj.get("corners") if valid else None
        corners = corners if isinstance(corners, dict) else {}
        for short, key in CORNERS:
            corner = corners.get(key)
            target[short].append(_num(corner.get("force_kg")) if isinstance(corner, dict) else NAN)

    def _mode_index(self, value: Any) -> int:
        if not isinstance(value, str) or not value:
            return -1
        if value not in self.mode_names:
            if len(self.mode_names) >= 100:
                return -1
            self.mode_names.append(value)
        return self.mode_names.index(value)


def _part_signature(kind: str, folder: Path) -> list[tuple[Any, ...]]:
    """Size and mtime of part files. A new gamepad part must miss the cache."""
    signature: list[tuple[Any, ...]] = []
    for path in _sorted_parts(folder, ".jsonl"):
        try:
            stat = path.stat()
        except OSError:
            continue
        signature.append((kind, path.name, stat.st_size, stat.st_mtime_ns))
    return signature


def load_columns(take_dir: Path, part_paths: list[Path]) -> TakeColumns:
    """Parsed columns for a take, reusing the cache while files are unchanged.

    ``part_paths`` is the sensor list the caller already resolved. The
    signature also covers ``gamepad/``, so a pad file that appears while
    a take is still recording is parsed on the next request.
    """
    signature = _part_signature("sensors", take_dir / "sensors")
    # Prefer the caller's list when the sensors directory listing raced,
    # but still key off the files that will actually be read.
    if not signature:
        for path in part_paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            signature.append(("sensors", path.name, stat.st_size, stat.st_mtime_ns))
    signature.extend(_part_signature("gamepad", take_dir / "gamepad"))
    # A policy part or a rewritten context.json must miss the cache too.
    signature.extend(_part_signature("policy", take_dir / "policy"))
    context_path = take_dir / "context.json"
    try:
        stat = context_path.stat()
    except OSError:
        stat = None
    if stat is not None:
        signature.append(("context", context_path.name, stat.st_size, stat.st_mtime_ns))
    key = str(take_dir)
    sig = tuple(signature)
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and hit[0] == sig:
            _CACHE.move_to_end(key)
            return hit[1]
        # Parsing under the lock keeps two tabs from parsing the same take
        # twice. Other takes wait a few seconds at most.
        columns = _parse(part_paths, take_dir / "sensors")
        _CACHE[key] = (sig, columns)
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
        return columns


def clear_cache() -> None:
    """Forget every parsed take. Tests use this between temp folders."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _parse(paths: list[Path], sensors_dir: Path) -> TakeColumns:
    columns = TakeColumns(paths, sensors_dir)
    for part_index, path in enumerate(paths):
        try:
            handle = path.open("rb")
        except OSError:
            continue
        with handle:
            offset = 0
            line_no = 0
            for raw_line in handle:
                line_no += 1
                start = offset
                offset += len(raw_line)
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except ValueError:
                    # Covers JSONDecodeError and invalid UTF-8 in a torn line.
                    continue
                if not isinstance(payload, dict):
                    continue
                stamp = payload.get("t")
                if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
                    continue
                columns.append(payload, part_index, start, line_no)
    _read_gamepad(columns, sensors_dir.parent / "gamepad")
    # Local import: lab_policy imports this module's constants at load time.
    from take_view.lab_policy import attach_policy

    attach_policy(columns, sensors_dir.parent)
    return columns


def _sorted_parts(folder: Path, suffix: str) -> list[Path]:
    """``part-NNN.jsonl`` in numeric order. Missing folder is an empty list."""
    if not folder.is_dir():
        return []
    paths = [path for path in folder.glob(f"part-*{suffix}") if path.is_file()]

    def index(path: Path) -> int:
        match = _PART_RE.search(path.name)
        return int(match.group(1)) if match else 0

    paths.sort(key=index)
    return paths


def _read_gamepad(columns: TakeColumns, folder: Path) -> None:
    """Parse gamepad parts into native rows. Absent folder leaves them empty."""
    paths = _sorted_parts(folder, ".jsonl")
    columns.pad_paths = paths
    for part_index, path in enumerate(paths):
        try:
            handle = path.open("rb")
        except OSError:
            continue
        with handle:
            offset = 0
            line_no = 0
            for raw_line in handle:
                line_no += 1
                start = offset
                offset += len(raw_line)
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                stamp = payload.get("t")
                if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
                    continue
                columns.append_pad(payload, part_index, start, line_no)


_NO_JOINTS: list[Any] = [None] * JOINT_COUNT


def _fit(value: Any) -> list[Any]:
    """Exactly JOINT_COUNT items: pad a short array with gaps, trim a long one."""
    if type(value) is not list:
        return _NO_JOINTS
    if len(value) == JOINT_COUNT:
        return value
    return (value + _NO_JOINTS)[:JOINT_COUNT]


def _num(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return NAN
    number = float(value)
    return number if math.isfinite(number) else NAN


def _flag(value: Any) -> int:
    if value is True:
        return 1
    if value is False:
        return 0
    return -1


def _int(value: Any) -> int:
    """Non-negative counter or -1. Firmware counters never go negative."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return -1
    return min(value, 2**62)


def _small(value: Any) -> int:
    """Small code (mag, agc, mask) that fits int16, or -1."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 32767:
        return -1
    return value


def _flags_to_float(source: array) -> array:
    return array("d", (NAN if value < 0 else float(value) for value in source))


def _ints_to_float(source: array) -> array:
    return array("d", (NAN if value < 0 else float(value) for value in source))


def _diff(source: array, fn: Any) -> array:
    """Row-to-row difference where both sides are present, else NaN."""
    out = array("d", [NAN] if len(source) else [])
    for index in range(1, len(source)):
        before = source[index - 1]
        after = source[index]
        out.append(NAN if before < 0 or after < 0 else fn(before, after))
    return out
