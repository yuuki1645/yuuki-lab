# -*- coding: utf-8 -*-
"""Lab take listing, health summary, and null-preserving downsample."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from take_view import router as lab_router
from take_view import lab_takes
from take_view.lab_takes import LabError


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LAB_EXPERIMENTS_ROOT", str(tmp_path))
    app = FastAPI()
    app.include_router(lab_router.router)
    return TestClient(app)


def _row(
    t: float,
    *,
    corr0: float | None,
    overrun: bool = False,
    i2c: int = 0,
    foot_ok: bool = True,
    foot_kg: float = 1.0,
    left_ok: bool = False,
) -> dict:
    corr = [None] * 10
    corr[0] = corr0
    return {
        "t": t,
        "seq": int(t),
        "overrun": overrun,
        "cmd": [135.0] * 10,
        "corr": corr,
        "as_ok": [corr0 is not None, False, False, False, False, False, False, False, False, False],
        "mag": [0, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        "ina_ok": [True, False, False, False, False, False, False, False, False, False],
        "i2c_err": i2c,
        "servo_ok": False,
        "mode": "lab",
        "foot": {"ok": foot_ok, "force_kg": foot_kg if foot_ok else 0.0},
        "foot_left": {"ok": left_ok, "force_kg": 0.0},
    }


def _write_take(
    root: Path,
    day: str,
    take_id: str,
    rows: list[dict],
    *,
    meta: dict | None = None,
    events: list[str] | None = None,
    extra_part: list[dict] | None = None,
) -> None:
    year, month, day_num = day.split("-")
    take = root / year / month / day_num / take_id
    (take / "sensors").mkdir(parents=True)
    (take / "events").mkdir()
    (take / "sensors" / "part-000.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    if extra_part is not None:
        (take / "sensors" / "part-001.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in extra_part),
            encoding="utf-8",
            newline="\n",
        )
    if events is not None:
        (take / "events" / "part-000.log").write_text(
            "\n".join(events) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    payload = {
        "format_id": "core_take_v1",
        "take_id": take_id,
        "started_at": "2026-10-26T12:02:52.005+09:00",
        "started_unix": 1000.0,
        "recording": False,
        "notes": "",
        "sample_count": len(rows) + (len(extra_part) if extra_part else 0),
        "stop_reason": "USB \u30a8\u30e9\u30fc",
        "duration_sec": 12.5,
        "open_parts": [],
    }
    if meta:
        payload.update(meta)
    (take / "meta.json").write_text(json.dumps(payload), encoding="utf-8", newline="\n")


def test_missing_root_lists_no_days(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path / "absent", monkeypatch)
    res = client.get("/api/lab/days")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert body["days"] == []


def test_list_ignores_index_file_and_reads_both_take_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_take(tmp_path, "2026-10-26", "004_120252", [_row(1.0, corr0=100.0)])
    _write_take(
        tmp_path,
        "2026-10-26",
        "095959",
        [_row(2.0, corr0=100.0)],
        meta={"started_unix": 900.0, "started_at": "2026-10-26T09:59:59+09:00"},
    )
    day_dir = tmp_path / "2026" / "10" / "26"
    (day_dir / ".last_index").write_text("4", encoding="utf-8")
    client = _client(tmp_path, monkeypatch)

    days = client.get("/api/lab/days")
    assert days.status_code == 200
    assert days.json()["days"] == [{"day": "2026-10-26", "take_count": 2}]

    takes = client.get("/api/lab/takes", params={"day": "2026-10-26"})
    assert takes.status_code == 200
    ids = [item["take_id"] for item in takes.json()["takes"]]
    assert ids == ["004_120252", "095959"]


def test_summary_keeps_gaps_and_foot_zero_when_not_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rows = [
        _row(1000.0, corr0=100.0, overrun=True, i2c=10, foot_ok=True, foot_kg=1.0),
        _row(1001.0, corr0=None, i2c=15, foot_ok=False, foot_kg=0.0),
    ]
    _write_take(
        tmp_path,
        "2026-10-26",
        "004_120252",
        rows[:1],
        extra_part=rows[1:],
        events=[
            "2026-10-26T12:02:52.089+09:00  \u8a18\u9332\u958b\u59cb",
            "not-an-event-stamp",
        ],
    )
    client = _client(tmp_path, monkeypatch)
    detail = client.get("/api/lab/takes/2026-10-26/004_120252")
    assert detail.status_code == 200
    body = detail.json()
    assert body["sample_count_read"] == 2
    assert body["parts_read"] == 2
    assert body["overrun_count"] == 1
    assert body["i2c_err_delta"] == 5
    joint0 = body["joints"][0]
    assert joint0["as_ok_ratio"] == 0.5
    assert joint0["tracking_samples"] == 1
    assert joint0["tracking_mean_abs_deg"] == pytest.approx(35.0)
    assert body["joints"][5]["as_ok_ratio"] == 0.0
    assert body["foot"]["ok_ratio"] == 0.5
    assert body["foot"]["force_min_kg"] == pytest.approx(1.0)
    assert body["foot_left"]["force_min_kg"] is None
    assert body["meta"]["stop_reason"] == "USB \u30a8\u30e9\u30fc"

    series = client.get(
        "/api/lab/takes/2026-10-26/004_120252/series",
        params={"joint": 0, "fields": "cmd,corr,foot_force_kg,foot_left_force_kg", "max_points": 10},
    )
    assert series.status_code == 200
    points = series.json()["points"]
    assert series.json()["downsampled"] is False
    assert points[0]["values"]["corr"] == pytest.approx(100.0)
    assert points[1]["values"]["corr"] is None
    assert points[1]["values"]["cmd"] == pytest.approx(135.0)
    assert points[0]["values"]["foot_force_kg"] == pytest.approx(1.0)
    assert points[1]["values"]["foot_force_kg"] is None
    assert points[0]["values"]["foot_left_force_kg"] is None

    events = client.get("/api/lab/takes/2026-10-26/004_120252/events")
    assert events.status_code == 200
    payload = events.json()
    assert payload["total"] == 2
    assert payload["events"][0]["text"] == "\u8a18\u9332\u958b\u59cb"
    assert payload["events"][0]["t_offset_sec"] == pytest.approx(0.084, abs=0.01)
    assert payload["events"][1]["t_iso"] is None


def test_downsample_null_bucket_stays_null(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rows = [
        _row(1.0, corr0=0.0),
        _row(2.0, corr0=None),
        _row(3.0, corr0=None),
        _row(4.0, corr0=None),
    ]
    _write_take(tmp_path, "2026-10-26", "004_120252", rows)
    client = _client(tmp_path, monkeypatch)
    series = client.get(
        "/api/lab/takes/2026-10-26/004_120252/series",
        params={"joint": 0, "fields": "corr", "max_points": 2},
    )
    assert series.status_code == 200
    body = series.json()
    assert body["downsampled"] is True
    assert body["point_count"] == 2
    assert body["points"][0]["values"]["corr"] == pytest.approx(0.0)
    assert body["points"][1]["values"]["corr"] is None


def test_bad_take_id_and_unknown_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_take(
        tmp_path,
        "2026-10-26",
        "004_120252",
        [_row(1.0, corr0=1.0)],
        meta={"format_id": "other"},
    )
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/lab/takes/2026-10-26/not_a_take").status_code == 400
    detail = client.get("/api/lab/takes/2026-10-26/004_120252")
    assert detail.status_code == 200
    assert detail.json()["meta"]["supported"] is False
    assert detail.json()["joints"] == []
    series = client.get(
        "/api/lab/takes/2026-10-26/004_120252/series",
        params={"joint": 0, "fields": "cmd"},
    )
    assert series.status_code == 422


def test_same_take_id_in_robot_and_sim_needs_side(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Serial numbers are counted separately, so the same folder name can exist twice."""
    day = "2026-11-28"
    take_id = "001_132301"
    year, month, day_num = day.split("-")
    robot = tmp_path / year / month / day_num / take_id
    sim = tmp_path / "sim" / year / month / day_num / take_id
    for folder, format_id in ((robot, "core_take_v1"), (sim, "sim_play_v1")):
        folder.mkdir(parents=True)
        (folder / "meta.json").write_text(
            json.dumps({"format_id": format_id, "take_id": take_id, "started_unix": 10.0, "sample_count": 1}),
            encoding="utf-8",
            newline="\n",
        )
    client = _client(tmp_path, monkeypatch)
    listed = client.get("/api/lab/takes", params={"day": day})
    assert listed.status_code == 200
    sides = sorted(item["side"] for item in listed.json()["takes"])
    assert sides == ["robot", "sim"]
    ambiguous = client.get(f"/api/lab/takes/{day}/{take_id}/analysis")
    assert ambiguous.status_code == 409
    opened = client.get(f"/api/lab/takes/{day}/{take_id}", params={"side": "sim"})
    assert opened.status_code == 200
    assert opened.json()["meta"]["side"] == "sim"
    assert opened.json()["meta"]["format_id"] == "sim_play_v1"


def test_path_cannot_escape_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LAB_EXPERIMENTS_ROOT", str(tmp_path))
    with pytest.raises(LabError) as caught:
        lab_takes._take_dir("2026-10-26", "..")
    assert caught.value.status_code == 400
    outside = tmp_path.parent / "secret.json"
    assert lab_takes._day_dir("2026-10-26").is_relative_to(tmp_path.resolve())
    assert not str(outside).startswith(str(lab_takes._day_dir("2026-10-26")))
