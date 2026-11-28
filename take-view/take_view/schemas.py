# -*- coding: utf-8 -*-
"""Lab take API shapes.

Sensor rows stay on disk. These models are meta, per-joint health, and
downsampled series. Missing measurements are null, never a fake zero.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LabDay(BaseModel):
    """One calendar day that contains at least one take folder."""

    day: str
    take_count: int


class LabDaysResponse(BaseModel):
    """Day index. available is false when the root directory is missing."""

    root: str
    available: bool
    days: list[LabDay]


class LabTakeMeta(BaseModel):
    """Fields copied from meta.json. day comes from the folder path."""

    day: str
    take_id: str
    format_id: str | None = None
    # "robot" is a real take. "sim" is an Isaac Lab playback under sim/.
    side: str = "robot"
    # Experiment name from context.json. Real takes leave this empty.
    name: str | None = None
    day_index: int | None = None
    started_at: str | None = None
    ended_at: str | None = None
    started_unix: float | None = None
    ended_unix: float | None = None
    recording: bool = False
    notes: str = ""
    hello: str | None = None
    port: str | None = None
    fw_ver: int | None = None
    sample_count: int | None = None
    # Policy rows written into policy/. None on core_take_v1, which has no such file.
    policy_count: int | None = None
    stop_reason: str | None = None
    duration_sec: float | None = None
    open_parts: list[str] = Field(default_factory=list)
    supported: bool = False


class LabTakesResponse(BaseModel):
    day: str
    takes: list[LabTakeMeta]


class LabJointSummary(BaseModel):
    """Health of one logical axis across the take."""

    index: int
    name: str
    as_ok_ratio: float | None = None
    ina_ok_ratio: float | None = None
    mag_mode: int | None = None
    tracking_mean_abs_deg: float | None = None
    tracking_max_abs_deg: float | None = None
    tracking_samples: int = 0


class LabFootSummary(BaseModel):
    """Foot slave reach and total force while samples were valid."""

    ok_ratio: float | None = None
    force_min_kg: float | None = None
    force_max_kg: float | None = None


class LabTakeDetail(BaseModel):
    """meta plus one pass over sensors/part-*.jsonl."""

    meta: LabTakeMeta
    tail_pending: bool = False
    sample_count_read: int = 0
    parts_read: int = 0
    overrun_count: int = 0
    i2c_err_start: int | None = None
    i2c_err_end: int | None = None
    i2c_err_delta: int | None = None
    servo_ok_ratio: float | None = None
    mode: str | None = None
    joints: list[LabJointSummary] = Field(default_factory=list)
    foot: LabFootSummary = Field(default_factory=LabFootSummary)
    foot_left: LabFootSummary = Field(default_factory=LabFootSummary)


class LabSeriesPoint(BaseModel):
    """One chart point. values omit nothing: a missing field is null."""

    t: float
    t_offset_sec: float
    values: dict[str, float | None]


class LabSeriesResponse(BaseModel):
    day: str
    take_id: str
    joint: int | None = None
    joint_name: str | None = None
    fields: list[str]
    sample_count: int
    point_count: int
    downsampled: bool
    points: list[LabSeriesPoint]


class LabEvent(BaseModel):
    t_iso: str | None = None
    t_offset_sec: float | None = None
    text: str


class LabEventsResponse(BaseModel):
    day: str
    take_id: str
    total: int
    truncated: bool
    events: list[LabEvent]
