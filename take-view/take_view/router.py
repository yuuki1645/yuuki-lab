# -*- coding: utf-8 -*-
"""Lab experiment reads. Files stay on the NAS; this API does not write them."""

from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from take_view.schemas import (
    LabDaysResponse,
    LabEventsResponse,
    LabSeriesResponse,
    LabTakeDetail,
    LabTakesResponse,
)
from take_view import lab_analysis
from take_view.lab_takes import LabError, get_events, get_series, get_take, list_days, list_takes

router = APIRouter(
    prefix="/api/lab",
    tags=["lab"],
)


def _raise_domain(exc: LabError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _json(payload: dict[str, Any]) -> JSONResponse:
    """Bulk numeric payloads skip response_model validation.

    The analysis responses carry tens of thousands of numbers. Pydantic
    would validate each one again; the service already emits JSON-safe
    values (gaps are null, never NaN).
    """
    return JSONResponse(content=payload)


@router.get("/days", response_model=LabDaysResponse)
def read_days() -> LabDaysResponse:
    """Calendar days that contain at least one take. Newest first."""
    return list_days()


@router.get("/takes", response_model=LabTakesResponse)
def read_takes(day: str = Query(..., min_length=10, max_length=10)) -> LabTakesResponse:
    """meta.json for one day. Does not scan sensor files."""
    try:
        return list_takes(day)
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}", response_model=LabTakeDetail)
def read_take(day: str, take_id: str, side: str | None = Query(None)) -> LabTakeDetail:
    """Health summary for one take. Null means the sensor was missing."""
    try:
        return get_take(day, take_id, side)
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}/series", response_model=LabSeriesResponse)
def read_series(
    day: str,
    take_id: str,
    fields: str = Query(..., description="Comma-separated cmd,corr,raw,unwrap,amp,watt,volt,foot_force_kg,foot_left_force_kg"),
    joint: int | None = Query(None, ge=0, le=9),
    max_points: int = Query(500, ge=1, le=2000),
    side: str | None = Query(None),
) -> LabSeriesResponse:
    """Chart series. Buckets with only missing samples stay null."""
    try:
        return get_series(day, take_id, fields=[fields], joint=joint, max_points=max_points, side=side)
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}/events", response_model=LabEventsResponse)
def read_events(
    day: str,
    take_id: str,
    limit: int = Query(300, ge=1, le=1000),
    side: str | None = Query(None),
) -> LabEventsResponse:
    """Event log lines for one take, oldest first."""
    try:
        return get_events(day, take_id, limit=limit, side=side)
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}/analysis")
def read_analysis(
    day: str,
    take_id: str,
    buckets: int = Query(lab_analysis.DEFAULT_BUCKETS, ge=10, le=lab_analysis.MAX_BUCKETS),
    side: str | None = Query(None),
) -> JSONResponse:
    """Health map, findings, per-joint and system stats, events, commands.

    The first call parses the take (a few seconds for 15 minutes of data);
    later calls hit the in-memory cache.
    """
    try:
        return _json(lab_analysis.get_analysis(day, take_id, buckets=buckets, side=side))
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}/window")
def read_window(
    day: str,
    take_id: str,
    channels: str = Query(..., description="Comma-separated ids such as j3.corr,sys.dt_ms,foot.cop_x"),
    t_from: float | None = Query(None, alias="from"),
    t_to: float | None = Query(None, alias="to"),
    max_points: int = Query(3000, ge=10, le=20000),
    side: str | None = Query(None),
) -> JSONResponse:
    """Raw rows for a short range, min/max/mean buckets for a long one."""
    try:
        return _json(
            lab_analysis.get_window(
                day,
                take_id,
                channels=[channels],
                t_from=t_from,
                t_to=t_to,
                max_points=max_points,
                side=side,
            )
        )
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}/stats")
def read_range_stats(
    day: str,
    take_id: str,
    channels: str = Query(...),
    t_from: float | None = Query(None, alias="from"),
    t_to: float | None = Query(None, alias="to"),
    side: str | None = Query(None),
) -> JSONResponse:
    """min / max (with their sample) / mean / std / percentiles for a range."""
    try:
        return _json(
            lab_analysis.get_range_stats(day, take_id, channels=[channels], t_from=t_from, t_to=t_to, side=side)
        )
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}/rows")
def read_rows(
    day: str,
    take_id: str,
    channels: str = Query(...),
    start: int = Query(0, ge=0),
    count: int = Query(100, ge=1, le=lab_analysis.MAX_ROWS),
    side: str | None = Query(None),
) -> JSONResponse:
    """Untouched rows by sample index for the data table."""
    try:
        return _json(lab_analysis.get_rows(day, take_id, channels=[channels], start=start, count=count, side=side))
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}/sample")
def read_sample(
    day: str,
    take_id: str,
    index: int | None = Query(None, ge=0),
    t: float | None = Query(None, description="Seconds since the first row; nearest row wins"),
    side: str | None = Query(None),
) -> JSONResponse:
    """One row exactly as written in sensors/part-NNN.jsonl, with its flags."""
    try:
        return _json(lab_analysis.get_sample(day, take_id, index=index, t=t, side=side))
    except LabError as exc:
        _raise_domain(exc)


@router.get("/takes/{day}/{take_id}/export.csv")
def read_export(
    day: str,
    take_id: str,
    channels: str = Query("", description="Empty means every channel"),
    t_from: float | None = Query(None, alias="from"),
    t_to: float | None = Query(None, alias="to"),
    side: str | None = Query(None),
) -> StreamingResponse:
    """Flattened CSV of a range. Gaps are empty cells."""
    try:
        filename, lines = lab_analysis.export_csv(
            day, take_id, channels=[channels], t_from=t_from, t_to=t_to, side=side
        )
    except LabError as exc:
        _raise_domain(exc)
    return StreamingResponse(
        lines,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
