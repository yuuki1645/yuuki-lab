# -*- coding: utf-8 -*-
"""Policy trace for core_take_v2.

``sensors/`` and ``policy/`` are two clocks. Their ``seq`` counters are not
the same counter, and a take can have a different number of rows in each.
Charts share the sensor clock: every policy channel is the policy row
nearest in UNIX ``t`` to that sensor row, and a match farther than
``POLICY_ALIGN_SEC`` stays a gap. The inspector still returns the policy
file's own line.

Joint order differs too. Policy arrays are left/right interleaved.
``context.json`` ``policy_joints[].firmware_index`` is the map onto the
screen's logical axes (right 0-4, left 5-9). Channel ``p0.obs`` is logical
axis 0, already remapped.

Angles in the policy file are radians from upright. ``j<N>.corr_rad`` on
the sensor side uses the same origin so the two can share one axis.
"""

from __future__ import annotations

import json
import math
from array import array
from bisect import bisect_left
from collections import Counter
from pathlib import Path
from typing import Any

from take_view.lab_columns import JOINT_COUNT, NAN, ChannelError
from take_view.lab_takes import JOINT_NAMES

# How far a policy row may sit from a sensor row and still be "the same moment".
POLICY_ALIGN_SEC = 0.1
# age_ms above this, and below the firmware's unknown sentinel, is stale.
POLICY_STALE_MS = 100.0
# |obs - corr_rad| above this is the policy and the encoder disagreeing.
POLICY_DIVERGE_RAD = 0.15
# action_rad past the envelope, while cmd_rad is still on it, is the limiter.
POLICY_CLIP_MARGIN = 0.02
# Playback does not run the real envelope. Past this, the robot would have clipped.
# Foot corners are rated 2 kg; a value sitting on that rating is saturated.
SIM_FOOT_SAT_KG = 1.99
# |gravity| far from 1, or a gyro faster than this, means the playback left upright.
SIM_GRAVITY_TOL = 0.08
SIM_GYRO_RAD_S = 1.0
# Firmware writes 65535 when it does not know how old a sample is.
AGE_UNKNOWN = 65535
OBS_COUNT = 38
AGE_COUNT = 12

# Where the 38 observations sit. Joint slots 0-9 follow policy order.
_OBS_GRAVITY = 10
_OBS_GYRO = 13
_OBS_FOOT = 16
_OBS_PHASE_SIN = 24
_OBS_PHASE_COS = 25
_OBS_VX = 26
_OBS_YAW = 27
_OBS_PREV = 28

# Policy index -> logical axis, when context.json is absent.
# Left/right interleaved: hip roll, hip pitch, knee, ankle pitch, ankle roll.
_DEFAULT_FW_OF_POLICY: tuple[int, ...] = (5, 0, 6, 1, 7, 2, 8, 3, 9, 4)
# Upright angle of each logical axis, degrees. RDS51150 rests at 135.
_DEFAULT_UPRIGHT: tuple[float, ...] = (135.0, 135.0, 0.0, 0.0, 135.0, 135.0, 135.0, 0.0, 0.0, 135.0)

# Fallback labels. A take's context.json replaces these and is not rewritten
# when the firmware constants change later.
_DEFAULT_ENUMS: dict[str, dict[str, str]] = {
    "reason": {
        "0": "\u5207",
        "1": "\u5b9f\u884c",
        "2": "\u95a2\u7bc0\u6b20\u6e2c",
        "3": "IMU\u6b20\u6e2c",
        "4": "\u8db3\u88cf\u6b20\u6e2c",
        "5": "\u76f4\u7acb\u3067\u306f\u306a\u3044",
        "6": "\u6545\u969c",
        "7": "\u76f4\u7acb\u7bc4\u56f2",
        "8": "\u76ee\u6a19\u56fa\u5b9a",
    },
    "safety": {
        "0": "\u306a\u3057",
        "1": "\u901f\u5ea6\u5236\u9650",
        "2": "\u76f4\u7acb\u3078\u623b\u3057\u3066\u3044\u308b",
        "3": "\u76ee\u6a19\u3092\u56fa\u5b9a",
    },
    "joint_flag": {
        "0": "\u6709\u52b9",
        "1": "\u6b20\u6e2c",
        "2": "\u98db\u3073",
        "3": "\u63fa\u308c",
    },
}

# Shown in the workbench's threshold list. Detection reads the constants above.
POLICY_THRESHOLDS: dict[str, float] = {
    "policy_align_sec": POLICY_ALIGN_SEC,
    "policy_stale_ms": POLICY_STALE_MS,
    "policy_diverge_rad": POLICY_DIVERGE_RAD,
    "policy_clip_margin_rad": POLICY_CLIP_MARGIN,
}

_PART_RE_PREFIX = "part-"


class TakeContext:
    """The copy of the contract stored inside one take folder.

    ``policy_of_fw[logical]`` is the policy-array index for that screen axis,
    or -1 when the contract does not mention it. ``upright`` is degrees.
    """

    def __init__(self) -> None:
        self.present = False
        self.joint_names: tuple[str, ...] = JOINT_NAMES
        self.upright: tuple[float, ...] = _DEFAULT_UPRIGHT
        # Servo model per logical axis. Empty means the take did not say,
        # which is the older RDS51150 + AS5600 + INA226 arrangement.
        self.servos: tuple[str, ...] = ("",) * JOINT_COUNT
        self.fw_of_policy: tuple[int, ...] = _DEFAULT_FW_OF_POLICY
        self.policy_of_fw: tuple[int, ...] = _invert(_DEFAULT_FW_OF_POLICY)
        self.action_scale = 0.25
        self.envelope_rad = 0.35
        self.learn_run: str | None = None
        self.checkpoint: str | None = None
        self.robot: str | None = None
        # Playback-only. Real takes leave these empty.
        self.experiment: str | None = None
        self.task: str | None = None
        self.side: str | None = None
        self.enums: dict[str, dict[str, str]] = {
            key: dict(value) for key, value in _DEFAULT_ENUMS.items()
        }

    def brief(self) -> dict[str, Any]:
        """What the workbench needs to label a v2 take. Small on purpose."""
        return {
            "learn_run": self.learn_run,
            "checkpoint": self.checkpoint,
            "robot": self.robot,
            "experiment": self.experiment,
            "task": self.task,
            "side": self.side,
            "action_scale": self.action_scale,
            "envelope_rad": self.envelope_rad,
            # Logical axis -> policy array index. The inspector uses this to
            # pick the matching slot out of obs / action / joint_flag.
            "policy_of_fw": list(self.policy_of_fw),
            "servos": list(self.servos),
            "enums": self.enums,
        }


class PolicyTable:
    """Native policy rows, plus channels gathered onto the sensor clock."""

    def __init__(self, context: TakeContext) -> None:
        self.context = context
        self.paths: list[Path] = []
        self.t = array("d")
        self.seq = array("q")
        self.part = array("h")
        self.offset = array("q")
        self.line = array("i")
        self.reason = array("h")
        self.safety = array("h")
        self.overrun = array("b")
        self.bearing = array("b")
        self.dist_ok = array("b")
        self.period_us = array("d")
        self.sense_us = array("d")
        self.policy_us = array("d")
        # Row-major. obs is 38 wide, the joint arrays are 10, age is 12.
        self.obs = array("d")
        self.action = array("d")
        self.action_rad = array("d")
        self.cmd_rad = array("d")
        self.flag = array("h")
        self.age = array("i")
        self._native: dict[str, array] = {}
        self._aligned: dict[tuple[int, str], array] = {}
        self._match: array | None = None
        self._match_n = -1

    @property
    def n(self) -> int:
        return len(self.t)

    def read(self, folder: Path) -> None:
        """Parse part-NNN.jsonl in numeric order. A missing folder is empty."""
        self.paths = _sorted_parts(folder)
        for part_index, path in enumerate(self.paths):
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
                    self._append(payload, part_index, start, line_no)

    def summary(self, origin: float) -> dict[str, Any]:
        """Counts from the policy file itself, not from the sensor grid."""
        count = self.n
        if count == 0:
            return {}
        span = self.t[-1] - self.t[0]
        rate = (count - 1) / span if count > 1 and span > 0 else None
        action_rows = 0
        overrun_count = 0
        reasons: Counter[int] = Counter()
        safeties: Counter[int] = Counter()
        for index in range(count):
            if _row_has_action(self.action, index):
                action_rows += 1
            if self.overrun[index] == 1:
                overrun_count += 1
            if self.reason[index] >= 0:
                reasons[int(self.reason[index])] += 1
            if self.safety[index] >= 0:
                safeties[int(self.safety[index])] += 1
        return {
            "samples": count,
            "rate_hz": rate,
            "start_offset": self.t[0] - origin,
            "end_offset": self.t[-1] - origin,
            "action_rows": action_rows,
            "overrun_count": overrun_count,
            "reason_counts": {str(key): reasons[key] for key in sorted(reasons)},
            "safety_counts": {str(key): safeties[key] for key in sorted(safeties)},
        }

    def at(self, unix_t: float, origin: float) -> dict[str, Any] | None:
        """Policy row nearest to ``unix_t``, or None when nothing is close."""
        index = self._nearest_index(unix_t)
        if index is None:
            return None
        path = self.paths[self.part[index]]
        raw_line = _read_at(path, self.offset[index])
        row: dict[str, Any] | None = None
        if raw_line:
            try:
                parsed = json.loads(raw_line)
            except ValueError:
                parsed = None
            row = parsed if isinstance(parsed, dict) else None
        return {
            "t": float(self.t[index]),
            "t_offset": float(self.t[index] - origin),
            "part": f"policy/{path.name}",
            "line": int(self.line[index]),
            "raw_line": raw_line,
            "row": row,
        }

    def channel(self, sensor_t: array, name: str) -> array:
        """One channel gathered onto ``sensor_t``. Cached per sensor length."""
        key = (len(sensor_t), name)
        cached = self._aligned.get(key)
        if cached is not None:
            return cached
        native = self._native_series(name)
        aligned = self._project(sensor_t, native)
        self._aligned[key] = aligned
        return aligned

    def match_sensor(self, sensor_t: array) -> array:
        """Policy-row index for each sensor row, or -1 when none is close."""
        return self._match_rows(sensor_t)

    # ----- native series ------------------------------------------------

    def _native_series(self, name: str) -> array:
        cached = self._native.get(name)
        if cached is not None:
            return cached
        built = self._build_native(name)
        self._native[name] = built
        return built

    def _build_native(self, name: str) -> array:
        scope, _, field = _split_policy_channel(name)
        if scope == "p":
            joint = int(name[1:name.index(".")])
            return self._joint_native(joint, field)
        if scope == "imu":
            return self._imu_native(field)
        if scope == "pf":
            return self._foot_native(field)
        return self._scalar_native(field)

    def _joint_native(self, joint: int, field: str) -> array:
        """``joint`` is a logical axis. Values come from the policy slot."""
        slot = self.context.policy_of_fw[joint] if 0 <= joint < JOINT_COUNT else -1
        if slot < 0 or self.n == 0:
            return array("d", [NAN] * self.n)
        if field == "obs":
            return _column(self.obs, OBS_COUNT, slot, self.n)
        if field == "prev":
            return _column(self.obs, OBS_COUNT, _OBS_PREV + slot, self.n)
        if field == "action":
            return _column(self.action, JOINT_COUNT, slot, self.n)
        if field == "action_rad":
            return _column(self.action_rad, JOINT_COUNT, slot, self.n)
        if field == "cmd_rad":
            return _column(self.cmd_rad, JOINT_COUNT, slot, self.n)
        if field == "clip":
            wanted = _column(self.action_rad, JOINT_COUNT, slot, self.n)
            sent = _column(self.cmd_rad, JOINT_COUNT, slot, self.n)
            return array(
                "d",
                (
                    NAN if math.isnan(left) or math.isnan(right) else left - right
                    for left, right in zip(wanted, sent)
                ),
            )
        if field == "flag":
            return _codes(_column_int(self.flag, JOINT_COUNT, slot, self.n), unknown=None)
        if field == "age":
            return _codes(_column_int(self.age, AGE_COUNT, slot, self.n), unknown=AGE_UNKNOWN)
        raise ChannelError(f"p{joint}.{field}")

    def _imu_native(self, field: str) -> array:
        axes = {"gx": 0, "gy": 1, "gz": 2, "wx": 0, "wy": 1, "wz": 2}
        if field == "gmag":
            gx = _column(self.obs, OBS_COUNT, _OBS_GRAVITY, self.n)
            gy = _column(self.obs, OBS_COUNT, _OBS_GRAVITY + 1, self.n)
            gz = _column(self.obs, OBS_COUNT, _OBS_GRAVITY + 2, self.n)
            return array(
                "d",
                (
                    NAN if math.isnan(x) or math.isnan(y) or math.isnan(z) else math.sqrt(x * x + y * y + z * z)
                    for x, y, z in zip(gx, gy, gz)
                ),
            )
        if field in ("gx", "gy", "gz"):
            return _column(self.obs, OBS_COUNT, _OBS_GRAVITY + axes[field], self.n)
        if field in ("wx", "wy", "wz"):
            return _column(self.obs, OBS_COUNT, _OBS_GYRO + axes[field], self.n)
        raise ChannelError(f"imu.{field}")

    def _foot_native(self, field: str) -> array:
        order = ("l_tl", "l_tr", "l_bl", "l_br", "r_tl", "r_tr", "r_bl", "r_br")
        if field not in order:
            raise ChannelError(f"pf.{field}")
        return _column(self.obs, OBS_COUNT, _OBS_FOOT + order.index(field), self.n)

    def _scalar_native(self, field: str) -> array:
        if field == "reason":
            return _codes(self.reason, unknown=None)
        if field == "safety":
            return _codes(self.safety, unknown=None)
        if field == "bearing":
            return _flags(self.bearing)
        if field == "dist":
            return _flags(self.dist_ok)
        if field == "overrun":
            return _flags(self.overrun)
        if field == "period_us":
            return self.period_us
        if field == "sense_us":
            return self.sense_us
        if field == "policy_us":
            return self.policy_us
        if field == "dt_ms":
            return _dt_ms(self.t)
        if field == "phase_sin":
            return _column(self.obs, OBS_COUNT, _OBS_PHASE_SIN, self.n)
        if field == "phase_cos":
            return _column(self.obs, OBS_COUNT, _OBS_PHASE_COS, self.n)
        if field == "vx":
            return _column(self.obs, OBS_COUNT, _OBS_VX, self.n)
        if field == "yaw":
            return _column(self.obs, OBS_COUNT, _OBS_YAW, self.n)
        if field == "age_imu":
            return _codes(_column_int(self.age, AGE_COUNT, 10, self.n), unknown=AGE_UNKNOWN)
        if field == "age_foot":
            return _codes(_column_int(self.age, AGE_COUNT, 11, self.n), unknown=AGE_UNKNOWN)
        raise ChannelError(f"pol.{field}")

    # ----- alignment ----------------------------------------------------

    def _project(self, sensor_t: array, native: array) -> array:
        matched = self._match_rows(sensor_t)
        out = array("d")
        width = len(native)
        for src in matched:
            out.append(NAN if src < 0 or src >= width else native[src])
        return out

    def _match_rows(self, sensor_t: array) -> array:
        if self._match is not None and self._match_n == len(sensor_t):
            return self._match
        out = array("i")
        for stamp in sensor_t:
            found = self._nearest_index(float(stamp))
            out.append(-1 if found is None else found)
        self._match = out
        self._match_n = len(sensor_t)
        return out

    def _nearest_index(self, stamp: float) -> int | None:
        count = self.n
        if count == 0:
            return None
        index = bisect_left(self.t, stamp)
        best: int | None = None
        best_dt = POLICY_ALIGN_SEC
        for cand in (index - 1, index):
            if 0 <= cand < count:
                delta = abs(self.t[cand] - stamp)
                if delta <= best_dt:
                    best_dt = delta
                    best = cand
        return best

    def _append(self, row: dict[str, Any], part_index: int, offset: int, line_no: int) -> None:
        self.t.append(float(row["t"]))
        self.part.append(part_index)
        self.offset.append(offset)
        self.line.append(line_no)
        self.seq.append(_int(row.get("seq")))
        self.reason.append(_code(row.get("reason")))
        self.safety.append(_code(row.get("safety")))
        self.overrun.append(_bit(row.get("overrun")))
        self.bearing.append(_bit(row.get("foot_bearing")))
        self.dist_ok.append(_bit(row.get("dist_ok")))
        self.period_us.append(_num(row.get("t_period_us")))
        self.sense_us.append(_num(row.get("t_sense_us")))
        self.policy_us.append(_num(row.get("t_policy_us")))
        self.obs.extend(_nums(row.get("obs"), OBS_COUNT))
        self.action.extend(_nums(row.get("action"), JOINT_COUNT))
        self.action_rad.extend(_nums(row.get("action_rad"), JOINT_COUNT))
        self.cmd_rad.extend(_nums(row.get("cmd_rad"), JOINT_COUNT))
        self.flag.extend(_codes_list(row.get("joint_flag"), JOINT_COUNT))
        self.age.extend(_codes_list(row.get("age_ms"), AGE_COUNT))


def load_context(take_dir: Path) -> TakeContext:
    """Read context.json. A missing or unreadable file keeps the defaults."""
    context = TakeContext()
    path = take_dir / "context.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return context
    if not isinstance(raw, dict):
        return context
    context.present = True
    _apply_joints(context, raw.get("firmware_joints"), raw.get("policy_joints"))
    policy = raw.get("policy") if isinstance(raw.get("policy"), dict) else {}
    scale = policy.get("action_scale")
    envelope = policy.get("envelope_rad")
    if isinstance(scale, (int, float)) and not isinstance(scale, bool):
        context.action_scale = float(scale)
    if isinstance(envelope, (int, float)) and not isinstance(envelope, bool):
        context.envelope_rad = float(envelope)
    project = raw.get("project") if isinstance(raw.get("project"), dict) else {}
    context.learn_run = _text(project.get("learn_run"))
    context.checkpoint = _text(project.get("checkpoint"))
    context.robot = _text(project.get("robot"))
    context.task = _text(project.get("task"))
    context.experiment = _text(raw.get("experiment"))
    context.side = _text(raw.get("side"))
    enums = raw.get("enums") if isinstance(raw.get("enums"), dict) else {}
    for key in ("reason", "safety", "joint_flag"):
        table = enums.get(key)
        if isinstance(table, dict):
            cleaned = {str(code): text for code, text in table.items() if isinstance(text, str)}
            if cleaned:
                context.enums[key] = cleaned
    return context


def attach_policy(columns: Any, take_dir: Path) -> None:
    """Load context.json and policy parts onto a parsed sensor table.

    Called at the end of sensor parsing. v1 takes have neither file; the
    table stays empty and every policy channel is a gap.
    """
    context = load_context(take_dir)
    table = PolicyTable(context)
    table.read(take_dir / "policy")
    columns.context = context
    columns.policy = table
    columns.upright = context.upright
    # A playback has policy rows and no sensor file. Those rows become the
    # chart clock. A real take already has sensor rows, so this is a no-op.
    adopt_policy_clock(columns)


def adopt_policy_clock(columns: Any) -> None:
    """Make policy rows the analysis clock when the take has no sensor file.

    Wall-clock ``t`` on a simulation is whenever the PC finished a step, so
    the gaps are irregular (a tenth of a second, then a quarter). The chart
    axis is the sum of ``t_period_us`` (30 Hz in the file). ``columns.t``
    stays the file's UNIX ``t`` so nearest-time projection hits the same row.

    Sensor detectors must not run on these rows. They are blank on purpose:
    there is no encoder, and a column of gaps is not ten broken sensors.
    """
    table: PolicyTable | None = getattr(columns, "policy", None)
    if columns.n or table is None or table.n == 0 or columns.paths:
        return
    columns.paths = list(table.paths)
    columns.part_prefix = "policy"
    columns.sim_clock = True
    sim_off = array("d")
    cursor = 0.0
    for index in range(table.n):
        sim_off.append(cursor)
        period = table.period_us[index]
        step = period / 1_000_000.0 if period == period and period > 0 else (1.0 / 30.0)
        sense = table.sense_us[index]
        seq = table.seq[index]
        columns.append(
            {
                "t": float(table.t[index]),
                "seq": int(seq) if seq >= 0 else None,
                "period_us": None if period != period else float(period),
                "sense_us": None if sense != sense else float(sense),
            },
            int(table.part[index]),
            int(table.offset[index]),
            int(table.line[index]),
        )
        cursor += step
    # Drop any wall-clock axis cached while the rows were appended.
    columns._t_off = None
    columns._sim_off = sim_off


def apply_sim_flags(columns: Any, flags: Any) -> None:
    """Findings that only make sense for a playback.

    ``action_rad`` and ``cmd_rad`` are both pre-clip and nearly equal, so the
    real-robot clip detector (the difference) stays quiet. The useful check
    is whether the command would have hit the robot's envelope. Foot corners
    sitting on 2 kg are the rated saturation, not a healthy load.
    """
    if not getattr(columns, "sim_clock", False):
        return
    table: PolicyTable | None = getattr(columns, "policy", None)
    if table is None or table.n == 0 or columns.n == 0:
        return
    envelope = table.context.envelope_rad + POLICY_CLIP_MARGIN
    policy_of_fw = table.context.policy_of_fw
    count = min(columns.n, table.n)
    for index in range(count):
        base = index * OBS_COUNT
        _flag_sim_tilt(table, flags, index, base)
        _flag_sim_feet(table, flags, index, base)
        for joint in range(JOINT_COUNT):
            slot = policy_of_fw[joint]
            if slot < 0:
                continue
            value = _flat_float(table.action_rad, JOINT_COUNT, index, slot)
            if value == value and abs(value) > envelope:
                lane = f"j{joint}"
                if lane in flags.sev:
                    flags.add("sim_envelope", lane, index, 2, value)


def _flag_sim_tilt(table: PolicyTable, flags: Any, index: int, base: int) -> None:
    """Gravity leaving straight down, or a fast gyro, on the policy lane."""
    if "policy" not in flags.sev:
        return
    obs = table.obs
    gx = obs[base + _OBS_GRAVITY]
    gy = obs[base + _OBS_GRAVITY + 1]
    gz = obs[base + _OBS_GRAVITY + 2]
    wx = obs[base + _OBS_GYRO]
    wy = obs[base + _OBS_GYRO + 1]
    wz = obs[base + _OBS_GYRO + 2]
    peak = NAN
    if gx == gx and gy == gy and gz == gz:
        magnitude = math.hypot(gx, gy, gz)
        if abs(magnitude - 1.0) > SIM_GRAVITY_TOL:
            peak = magnitude
    if wx == wx and wy == wy and wz == wz:
        speed = math.hypot(wx, wy, wz)
        if speed > SIM_GYRO_RAD_S and (peak != peak or speed > peak):
            peak = speed
    if peak == peak:
        flags.add("sim_tilt", "policy", index, 2, peak)


def _flag_sim_feet(table: PolicyTable, flags: Any, index: int, base: int) -> None:
    """A corner at the 2 kg rating is saturated. Left and right are separate lanes."""
    obs = table.obs
    for lane, start in (("foot_left", 0), ("foot", 4)):
        if lane not in flags.sev:
            continue
        peak = NAN
        for offset in range(4):
            value = obs[base + _OBS_FOOT + start + offset]
            if value == value and (peak != peak or value > peak):
                peak = value
        if peak == peak and peak >= SIM_FOOT_SAT_KG:
            flags.add("foot_saturated", lane, index, 2, peak)


def apply_policy_flags(columns: Any, flags: Any) -> None:
    """Turn policy rows into findings on the sensor clock.

    One flag per sensor row, so two policy rows that land on the same sensor
    sample do not double-count. ``reason`` 0 (off) and 1 (running) are the
    normal states and are not findings. A missing joint (flag 1) is already
    covered by the sensor detectors.
    """
    table: PolicyTable | None = getattr(columns, "policy", None)
    if table is None or table.n == 0 or columns.n == 0:
        return
    if "policy" not in flags.sev:
        return
    matched = table.match_sensor(columns.t)
    envelope = table.context.envelope_rad
    upright = table.context.upright
    seen: set[tuple[str, str, int]] = set()

    def once(kind: str, lane: str, index: int, severity: int, value: float) -> None:
        key = (kind, lane, index)
        if key in seen or lane not in flags.sev:
            return
        seen.add(key)
        flags.add(kind, lane, index, severity, value)

    for index in range(columns.n):
        src = matched[index]
        if src < 0:
            continue
        safety = table.safety[src]
        if safety == 1 or safety == 2:
            once("policy_safety", "policy", index, 2, float(safety))
        elif safety >= 3:
            once("policy_safety", "policy", index, 2, float(safety))
        reason = table.reason[src]
        if reason in (2, 3, 4, 6):
            once("policy_reason", "policy", index, 3, float(reason))
        elif reason in (5, 7):
            once("policy_reason", "policy", index, 2, float(reason))
        elif reason == 8:
            once("policy_reason", "policy", index, 1, float(reason))

        age_imu = _age_at(table, src, 10)
        if age_imu is not None and age_imu > POLICY_STALE_MS:
            once("policy_stale", "policy", index, 1, age_imu)

        for joint in range(JOINT_COUNT):
            slot = table.context.policy_of_fw[joint]
            if slot < 0:
                continue
            flag = _flat_int(table.flag, JOINT_COUNT, src, slot)
            lane = f"j{joint}"
            if flag in (2, 3):
                once("policy_flag", lane, index, 2, float(flag))
            age = _age_at(table, src, slot)
            if flag == 0 and age is not None and age > POLICY_STALE_MS:
                once("policy_stale", lane, index, 1, age)
            if flag != 0:
                continue
            action = _flat_float(table.action, JOINT_COUNT, src, slot)
            wanted = _flat_float(table.action_rad, JOINT_COUNT, src, slot)
            sent = _flat_float(table.cmd_rad, JOINT_COUNT, src, slot)
            if (
                not math.isnan(action)
                and not math.isnan(wanted)
                and not math.isnan(sent)
                and abs(wanted) > envelope + POLICY_CLIP_MARGIN
                and abs(sent) <= envelope + 0.005
            ):
                once("policy_clip", lane, index, 2, wanted - sent)
            obs = _flat_float(table.obs, OBS_COUNT, src, slot)
            corr = columns.joint_float["corr"][joint][index]
            if math.isnan(obs) or math.isnan(corr):
                continue
            measured = (corr - upright[joint]) * math.pi / 180.0
            gap = obs - measured
            if abs(gap) > POLICY_DIVERGE_RAD:
                once("policy_diverge", lane, index, 2, gap)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _apply_joints(context: TakeContext, firmware: Any, policy: Any) -> None:
    names = list(context.joint_names)
    upright = list(context.upright)
    servos = list(context.servos)
    if isinstance(firmware, list):
        for item in firmware:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            if not isinstance(index, int) or not 0 <= index < JOINT_COUNT:
                continue
            label = item.get("name")
            if isinstance(label, str) and label:
                names[index] = label
            angle = item.get("upright_deg")
            if isinstance(angle, (int, float)) and not isinstance(angle, bool):
                upright[index] = float(angle)
            # SM105BL reports its own angle. RDS51150 still uses AS5600.
            kind = item.get("servo")
            if isinstance(kind, str) and kind:
                servos[index] = kind
    fw_of_policy = list(context.fw_of_policy)
    if isinstance(policy, list):
        for item in policy:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            fw = item.get("firmware_index")
            if (
                isinstance(index, int)
                and isinstance(fw, int)
                and 0 <= index < JOINT_COUNT
                and 0 <= fw < JOINT_COUNT
            ):
                fw_of_policy[index] = fw
                # Sim context has policy_joints and no firmware_joints.
                # Keep a name the firmware list already set.
                label = item.get("name")
                if isinstance(label, str) and label and names[fw] == JOINT_NAMES[fw]:
                    names[fw] = label
                kind = item.get("servo")
                if isinstance(kind, str) and kind and not servos[fw]:
                    servos[fw] = kind
    context.joint_names = tuple(names)
    context.upright = tuple(upright)
    context.servos = tuple(servos)
    context.fw_of_policy = tuple(fw_of_policy)
    context.policy_of_fw = _invert(context.fw_of_policy)


def _invert(fw_of_policy: tuple[int, ...]) -> tuple[int, ...]:
    """Logical axis -> policy slot. -1 when no policy slot points at it."""
    out = [-1] * JOINT_COUNT
    for slot, fw in enumerate(fw_of_policy):
        if 0 <= fw < JOINT_COUNT and out[fw] < 0:
            out[fw] = slot
    return tuple(out)


def _split_policy_channel(name: str) -> tuple[str, int | None, str]:
    """``p3.obs`` / ``imu.gx`` / ``pol.reason`` / ``pf.l_tl``."""
    if name.startswith("p") and name[1:2].isdigit():
        joint_text, _, field = name.partition(".")
        return "p", int(joint_text[1:]), field
    scope, _, field = name.partition(".")
    return scope, None, field


def _sorted_parts(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    paths = [path for path in folder.glob("part-*.jsonl") if path.is_file()]

    def index(path: Path) -> int:
        stem = path.stem
        digits = stem[len(_PART_RE_PREFIX):] if stem.startswith(_PART_RE_PREFIX) else ""
        return int(digits) if digits.isdigit() else 0

    paths.sort(key=index)
    return paths


def _column(flat: array, width: int, index: int, count: int) -> array:
    if count == 0 or len(flat) < width:
        return array("d", [NAN] * count)
    return flat[index::width]


def _column_int(flat: array, width: int, index: int, count: int) -> array:
    if count == 0 or len(flat) < width:
        return array("i")
    return flat[index::width]


def _flat_float(flat: array, width: int, row: int, index: int) -> float:
    position = row * width + index
    if position >= len(flat):
        return NAN
    return float(flat[position])


def _flat_int(flat: array, width: int, row: int, index: int) -> int:
    position = row * width + index
    if position >= len(flat):
        return -1
    return int(flat[position])


def _age_at(table: PolicyTable, row: int, index: int) -> float | None:
    value = _flat_int(table.age, AGE_COUNT, row, index)
    if value < 0 or value >= AGE_UNKNOWN:
        return None
    return float(value)


def _row_has_action(flat: array, row: int) -> bool:
    start = row * JOINT_COUNT
    for value in flat[start:start + JOINT_COUNT]:
        if value == value:
            return True
    return False


def _codes(source: array, unknown: int | None) -> array:
    out = array("d")
    for value in source:
        if value < 0 or (unknown is not None and value >= unknown):
            out.append(NAN)
        else:
            out.append(float(value))
    return out


def _flags(source: array) -> array:
    return array("d", (NAN if value < 0 else float(value) for value in source))


def _dt_ms(stamps: array) -> array:
    out = array("d", [NAN] if stamps else [])
    for index in range(1, len(stamps)):
        out.append((stamps[index] - stamps[index - 1]) * 1000.0)
    return out


def _nums(value: Any, width: int) -> list[float]:
    items = value if isinstance(value, list) else []
    out: list[float] = []
    for index in range(width):
        out.append(_num(items[index]) if index < len(items) else NAN)
    return out


def _codes_list(value: Any, width: int) -> list[int]:
    items = value if isinstance(value, list) else []
    out: list[int] = []
    for index in range(width):
        out.append(_code(items[index]) if index < len(items) else -1)
    return out


def _num(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return NAN
    number = float(value)
    return number if math.isfinite(number) else NAN


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return -1
    return value


def _code(value: Any) -> int:
    """Small non-negative code, or -1. Floats are not codes."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return -1
    return value if value <= 65535 else -1


def _bit(value: Any) -> int:
    """True/1 and False/0. Anything else is unknown.

    Policy overrun is recorded as 0/1, while foot_bearing is a JSON bool.
    ``True == 1`` in Python, so the bool check has to come first.
    """
    if value is True:
        return 1
    if value is False:
        return 0
    if value == 1:
        return 1
    if value == 0:
        return 0
    return -1


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _read_at(path: Path, offset: int) -> str | None:
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            line = handle.readline()
    except OSError:
        return None
    return line.decode("utf-8", errors="replace").rstrip("\r\n")
