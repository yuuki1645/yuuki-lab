# -*- coding: utf-8 -*-
"""Anomaly detection, windows, stats and raw rows on a synthetic take.

The synthetic take is 20 Hz for 12 seconds and plants one example of each
problem at a known row, plus the situations that must NOT be flagged (a leg
that is not plugged in yet, a rail switched off, a constant offset).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from take_view import router as lab_router
from take_view import lab_columns

DAY = "2026-10-26"
TAKE = "004_120252"
BASE = f"/api/lab/takes/{DAY}/{TAKE}"
ROWS = 240
DT = 0.05
# Sensor t is UNIX seconds and event lines carry local ISO stamps. Both must
# describe the same instants for markers to line up, as on the real rig.
STARTED_AT = "2026-10-26T12:02:47.000+09:00"
T0 = datetime.fromisoformat(STARTED_AT).timestamp()


@pytest.fixture(autouse=True)
def _fresh_cache():
    lab_columns.clear_cache()
    yield
    lab_columns.clear_cache()


def _client(root: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LAB_EXPERIMENTS_ROOT", str(root))
    app = FastAPI()
    app.include_router(lab_router.router)
    return TestClient(app)


def _row(i: int) -> dict:
    """One sensor row with the planted problems for row i."""
    legs_online = i >= 10
    seq = 1000 + i + (1 if i >= 100 else 0)  # one lost cycle at row 100
    cmd = [135.0] * 10
    corr = [135.0] * 10
    raw = [200.0] * 10
    as_ok = [legs_online] * 10
    mag = [0 if legs_online else 255] * 10
    amp = [0.1] * 10
    volt = [12.0] * 10
    out_mask = 1 if i >= 20 else 0  # axis 0 driven from row 20

    # Axis 0: constant +10 degree offset while driven, plus a 20 degree
    # excursion on rows 150-155 (transient tracking error).
    if i >= 20:
        corr[0] = 145.0 + (20.0 if 150 <= i <= 155 else 0.0)
    # Axis 3: encoder dropout with I2C failure on rows 50-59.
    if 50 <= i <= 59:
        as_ok[3] = False
        mag[3] = 4
        corr[3] = None
        raw[3] = None
    # Axis 1: over-current spike on row 120.
    if i == 120:
        amp[1] = 3.0
    # Axis 2: short sag on rows 130-132 that recovers; then the rail is
    # switched off from row 200 and decays (must not be a sag).
    if 130 <= i <= 132:
        volt[2] = 9.0
    if i >= 200:
        volt[2] = max(0.3, 12.0 - (i - 200) * 2.0)
    if not legs_online:
        corr = [None] * 10
        raw = [None] * 10
        volt = [None] * 10
        amp = [None] * 10

    return {
        "t": T0 + i * DT,
        "seq": seq,
        "period_us": 50000,
        "loop_us": 900,
        "sense_us": 10,
        "jitter_us": 0,
        "overrun": False,
        "cmd": cmd,
        "raw": raw,
        "unwrap": raw,
        "corr": corr,
        "as_ok": as_ok,
        "mag": mag,
        "agc": [128] * 10,
        "volt": volt,
        "amp": amp,
        "watt": [None] * 10,
        "ina_ok": [legs_online] * 10,
        "i2c_err": 5 + max(0, min(i, 59) - 49),
        "servo_ok": legs_online,
        "mode": "lab",
        "out_mask": out_mask,
        "map_ok": [legs_online] * 10,
        "foot": {
            "ok": legs_online,
            "seq": i,
            "mask": 15,
            "force_kg": 1.0,
            "corners": {
                "top_left": {"force_kg": 0.4},
                "top_right": {"force_kg": 0.4},
                "bottom_right": {"force_kg": 0.1},
                "bottom_left": {"force_kg": 0.1},
            },
        },
        "foot_left": {"ok": False, "seq": 0, "mask": 0, "force_kg": 0.0, "corners": {}},
    }


def _write_take(root: Path, *, stop_reason: str = "USB \u30a8\u30e9\u30fc") -> Path:
    year, month, day = DAY.split("-")
    take = root / year / month / day / TAKE
    (take / "sensors").mkdir(parents=True)
    (take / "events").mkdir()
    (take / "commands").mkdir()
    rows = [_row(i) for i in range(ROWS)]
    # Two parts so row locations cross a file boundary.
    for part, chunk in enumerate((rows[:120], rows[120:])):
        (take / "sensors" / f"part-{part:03d}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in chunk),
            encoding="utf-8",
            newline="\n",
        )
    # "joint 3 AS5600 missing" at +2.6 s (inside the I2C burst), ERROR at +11 s.
    (take / "events" / "part-000.log").write_text(
        "2026-10-26T12:02:49.600+09:00  12:02:49  \u95a2\u7bc03 AS5600 \u6b20\u6e2c  mag=I2C\n"
        "2026-10-26T12:02:58.000+09:00  12:02:58  ERROR  ClearCommError failed\n",
        encoding="utf-8",
        newline="\n",
    )
    (take / "commands" / "part-000.jsonl").write_text(
        json.dumps({"text": "OUT", "ch": 0, "on": True, "t": T0 + 1.0}) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    meta = {
        "format_id": "core_take_v1",
        "take_id": TAKE,
        "started_at": STARTED_AT,
        "started_unix": T0,
        "recording": False,
        "notes": "",
        "sample_count": ROWS,
        "stop_reason": stop_reason,
        "duration_sec": ROWS * DT,
        "open_parts": [],
    }
    (take / "meta.json").write_text(json.dumps(meta), encoding="utf-8", newline="\n")
    return take


def _finding(body: dict, finding_id: str) -> dict | None:
    return next((item for item in body["findings"] if item["id"] == finding_id), None)


def test_analysis_flags_planted_problems_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_take(tmp_path)
    client = _client(tmp_path, monkeypatch)
    res = client.get(f"{BASE}/analysis", params={"buckets": 24})
    assert res.status_code == 200
    body = res.json()
    assert body["sample_count"] == ROWS
    assert body["meta"]["take_id"] == TAKE
    assert body["tail_pending"] is False
    # v1 has no policy trace and no context.json.
    assert body["policy"] is None
    assert body["context"] is None

    dropout = _finding(body, "dropout:j3")
    assert dropout is not None
    assert dropout["severity"] == 3
    assert dropout["sample_count"] == 10
    assert dropout["intervals"][0]["start_index"] == 50
    assert dropout["detail"]["mag"] == {"4": 10}

    # The leg was simply not connected for the first rows: no data, not a failure.
    assert _finding(body, "nodata:j3")["severity"] == 1
    assert all(item["intervals"][0]["start_index"] >= 10 for item in body["findings"] if item["kind"] == "dropout")

    # Constant offset reported once; only the excursion is a tracking error.
    offset = _finding(body, "track_offset:j0")
    assert offset["detail"]["median_deg"] == pytest.approx(10.0)
    tracking = _finding(body, "tracking:j0")
    assert tracking["severity"] == 3
    assert tracking["intervals"][0]["start_index"] == 150
    assert tracking["sample_count"] == 6

    assert _finding(body, "overcurrent:j1")["peak_value"] == pytest.approx(3.0)

    sag = _finding(body, "undervolt:j2")
    assert sag is not None
    assert sag["sample_count"] == 3
    assert sag["intervals"][0]["start_index"] == 130

    drop = _finding(body, "seq_drop:link")
    assert drop["intervals"][0]["start_index"] == 100
    assert drop["detail"]["dropped_total"] == 1

    # The I2C burst lines up with axis 3 and the event text names it.
    i2c = _finding(body, "i2c:i2c")
    assert i2c["detail"]["related"][0]["joint"] == 3
    assert i2c["detail"]["mentioned"][0]["joint"] == 3

    assert _finding(body, "event_error:events")["severity"] == 3
    assert _finding(body, "abnormal_stop:events")["detail"]["stop_reason"] == "USB \u30a8\u30e9\u30fc"
    # Findings are ordered worst first.
    severities = [item["severity"] for item in body["findings"]]
    assert severities == sorted(severities, reverse=True)

    health = body["health"]
    assert health["buckets"] == 24
    lane3 = next(lane for lane in health["lanes"] if lane["id"] == "j3")
    bucket = int(50 * DT / health["bucket_sec"])
    assert lane3["sev"][bucket] == 3
    assert body["kinds"][lane3["kind"][bucket]] == "dropout"
    lane0 = next(lane for lane in health["lanes"] if lane["id"] == "j0")
    assert lane0["out"][-1] == 1.0

    assert body["out_spans"][0][0][0] == pytest.approx(20 * DT)
    assert body["events"][0]["joint"] == 3
    assert body["events"][1]["level"] == "error"
    assert body["commands"][0]["text"] == "OUT"

    stats = body["joint_stats"][3]
    assert stats["dropout_samples"] == 10
    assert stats["crit"] >= 1


def test_normal_stop_is_not_a_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_take(tmp_path, stop_reason="USB \u5207\u65ad")
    client = _client(tmp_path, monkeypatch)
    body = client.get(f"{BASE}/analysis").json()
    assert _finding(body, "abnormal_stop:events") is None


def test_window_raw_and_envelope_keep_spikes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_take(tmp_path)
    client = _client(tmp_path, monkeypatch)

    raw = client.get(f"{BASE}/window", params={"channels": "j1.amp,j3.corr", "from": 5.9, "to": 6.1}).json()
    assert raw["mode"] == "raw"
    assert 120 in raw["index"]
    assert raw["series"]["j1.amp"]["v"][raw["index"].index(120)] == pytest.approx(3.0)

    env = client.get(f"{BASE}/window", params={"channels": "j1.amp,j3.corr", "max_points": 20}).json()
    assert env["mode"] == "envelope"
    assert len(env["t"]) == 10
    # The one-row spike survives as a bucket max.
    assert max(value for value in env["series"]["j1.amp"]["max"] if value is not None) == pytest.approx(3.0)

    gap = client.get(f"{BASE}/window", params={"channels": "j3.corr", "from": 2.6, "to": 2.9}).json()
    inside = [value for index, value in zip(gap["index"], gap["series"]["j3.corr"]["v"]) if 52 <= index <= 57]
    assert inside and all(value is None for value in inside)


def test_stats_rows_sample_and_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_take(tmp_path)
    client = _client(tmp_path, monkeypatch)

    stats = client.get(f"{BASE}/stats", params={"channels": "j1.amp,j0.err", "from": 5.0, "to": 7.0}).json()
    amp = stats["stats"]["j1.amp"]
    assert amp["max"] == pytest.approx(3.0)
    assert amp["max_index"] == 120
    assert stats["stats"]["j0.err"]["p50"] == pytest.approx(10.0)

    rows = client.get(f"{BASE}/rows", params={"channels": "j3.corr,sys.seq_gap,j3.sev", "start": 48, "count": 4}).json()
    assert rows["index"] == [48, 49, 50, 51]
    assert rows["series"]["j3.corr"] == [135.0, 135.0, None, None]
    # The detector verdict per row: ok before the dropout, crit inside it.
    assert rows["series"]["j3.sev"] == [0.0, 0.0, 3.0, 3.0]
    offline = client.get(f"{BASE}/rows", params={"channels": "j3.sev", "start": 0, "count": 2}).json()
    assert offline["series"]["j3.sev"] == [1.0, 1.0]

    sample = client.get(f"{BASE}/sample", params={"index": 125}).json()
    assert sample["part"] == "sensors/part-001.jsonl"
    assert sample["line"] == 6
    assert sample["row"]["seq"] == 1000 + 125 + 1
    assert sample["raw_line"] == json.dumps(_row(125))
    by_time = client.get(f"{BASE}/sample", params={"t": 2.51}).json()
    assert by_time["index"] == 50
    assert by_time["flags"]["j3"]["kind"] == "dropout"

    csv = client.get(f"{BASE}/export.csv", params={"channels": "j3.corr,j1.amp", "from": 2.43, "to": 2.52})
    assert csv.status_code == 200
    lines = csv.text.strip().splitlines()
    assert lines[0] == "index,t_unix,t_offset_sec,j3.corr,j1.amp"
    assert lines[1].split(",")[0] == "49"
    # Row 50 is a dropout: the gap is an empty cell, never 0.
    assert lines[2].split(",")[3] == ""


def test_bad_channel_and_sample_point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_take(tmp_path)
    client = _client(tmp_path, monkeypatch)
    assert client.get(f"{BASE}/window", params={"channels": "j12.corr"}).status_code == 400
    assert client.get(f"{BASE}/window", params={"channels": "sys.nope"}).status_code == 400
    assert client.get(f"{BASE}/sample").status_code == 400


def _stick(forward: float) -> dict:
    return {
        "forward": forward,
        "lateral": 0.0,
        "vertical": 0.0,
        "raw_forward": 0.004,
        "raw_lateral": -0.004,
        "bumper": False,
        "trigger": 0.0,
    }


def _pad_row(offset: float, *, forward: float, accepted: bool, heel_z: float) -> dict:
    """One gamepad row. raw_* jitters at rest and must not count as a stick."""
    return {
        "t": T0 + offset,
        "connected": True,
        "homing": False,
        "left": _stick(forward),
        "right": _stick(0.0),
        "heel_left": [-0.1, 0.09, heel_z],
        "heel_right": [-0.1, -0.09, -0.64],
        "accepted_left": accepted,
        "accepted_right": False,
        "floor_hold_left": False,
        "floor_hold_right": False,
    }


def _window_value(body: dict, channel: str, index: int):
    pos = body["index"].index(index)
    return body["series"][channel]["v"][pos]


def test_gamepad_folds_onto_sensor_time_and_keeps_native_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Accepted bursts collapse onto sensor rows. The header still counts pad rows.

    Sensor rows are 20 Hz. A burst of three accepted rows plus a neutral
    row share one sensor interval: the chart's accepted flag is 1 and the
    stick holds the last value (0). A later empty interval holds the stick
    and clears accepted. A pad row after the last sensor row is counted
    and is not on the chart.
    """
    take = _write_take(tmp_path)
    client = _client(tmp_path, monkeypatch)
    assert client.get(f"{BASE}/analysis").json()["gamepad"] is None
    bare = client.get(f"{BASE}/export.csv", params={"from": 0, "to": 0.1})
    assert "pad.l_forward" not in bare.text.splitlines()[0]

    rows = [
        _pad_row(5.01, forward=0.4, accepted=True, heel_z=3.0),
        _pad_row(5.02, forward=0.4, accepted=True, heel_z=3.0),
        _pad_row(5.03, forward=0.4, accepted=True, heel_z=3.0),
        _pad_row(5.04, forward=0.0, accepted=False, heel_z=3.0),
        _pad_row(5.08, forward=0.8, accepted=False, heel_z=4.0),
        # After the last sensor row (11.95 s). Counted, not plotted.
        _pad_row(11.96, forward=0.3, accepted=True, heel_z=9.0),
    ]
    (take / "gamepad").mkdir()
    (take / "gamepad" / "part-000.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )

    body = client.get(f"{BASE}/analysis").json()
    pad = body["gamepad"]
    assert pad["samples"] == 6
    assert pad["stick_rows"] == 5
    assert pad["accepted_left"] == 4
    assert pad["accepted_left_runs"] == 2
    assert pad["accepted_right"] == 0
    assert pad["accepted_right_runs"] == 0
    assert pad["start_offset"] == pytest.approx(5.01, abs=1e-6)

    window = client.get(
        f"{BASE}/window",
        params={"channels": "pad.l_forward,pad.l_accepted,pad.l_heel_z", "from": 4.9, "to": 5.2},
    ).json()
    assert window["mode"] == "raw"
    # Index 100 is t=5.00 s, still before the first pad row.
    assert _window_value(window, "pad.l_forward", 100) is None
    assert _window_value(window, "pad.l_accepted", 100) is None
    # 5.01..5.04 share sensor index 101 (t=5.05). Last stick is 0, any accept is 1.
    assert _window_value(window, "pad.l_forward", 101) == pytest.approx(0.0)
    assert _window_value(window, "pad.l_accepted", 101) == pytest.approx(1.0)
    assert _window_value(window, "pad.l_heel_z", 101) == pytest.approx(3.0)
    # Next sensor row takes the 5.08 sample. Accepted does not hold.
    assert _window_value(window, "pad.l_forward", 102) == pytest.approx(0.8)
    assert _window_value(window, "pad.l_accepted", 102) == pytest.approx(0.0)
    assert _window_value(window, "pad.l_heel_z", 102) == pytest.approx(4.0)
    # Empty interval holds the stick and heel, and accepted stays 0.
    assert _window_value(window, "pad.l_forward", 103) == pytest.approx(0.8)
    assert _window_value(window, "pad.l_accepted", 103) == pytest.approx(0.0)
    assert _window_value(window, "pad.l_heel_z", 103) == pytest.approx(4.0)

    early = client.get(f"{BASE}/sample", params={"index": 100}).json()
    assert early["gamepad"] is None
    mid = client.get(f"{BASE}/sample", params={"index": 101}).json()
    assert mid["gamepad"]["part"] == "gamepad/part-000.jsonl"
    assert mid["gamepad"]["line"] == 4
    assert mid["gamepad"]["row"]["left"]["forward"] == 0.0
    assert mid["gamepad"]["row"]["accepted_left"] is False

    tail = client.get(
        f"{BASE}/window",
        params={"channels": "pad.l_forward,pad.l_accepted", "from": 11.9, "to": 12.0},
    ).json()
    assert _window_value(tail, "pad.l_forward", ROWS - 1) == pytest.approx(0.8)
    assert _window_value(tail, "pad.l_accepted", ROWS - 1) == pytest.approx(0.0)

    exported = client.get(f"{BASE}/export.csv", params={"channels": "", "from": 5.0, "to": 5.05})
    assert "pad.l_accepted" in exported.text.splitlines()[0]
    assert client.get(f"{BASE}/window", params={"channels": "pad.nope"}).status_code == 400


def test_cache_reloads_when_parts_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    take = _write_take(tmp_path)
    client = _client(tmp_path, monkeypatch)
    assert client.get(f"{BASE}/analysis").json()["sample_count"] == ROWS
    extra = _row(ROWS)
    (take / "sensors" / "part-002.jsonl").write_text(json.dumps(extra) + "\n", encoding="utf-8", newline="\n")
    assert client.get(f"{BASE}/analysis").json()["sample_count"] == ROWS + 1


def _v2_sensor(t: float) -> dict:
    """One quiet sensor row. Joint 0 sits on its 135 degree upright."""
    return {
        "t": t,
        "seq": 1,
        "period_us": 33000,
        "loop_us": 2000,
        "sense_us": 1000,
        "jitter_us": 0,
        "overrun": False,
        "cmd": [135.0, 135.0, 0.0, 0.0, 135.0, 135.0, 135.0, 0.0, 0.0, 135.0],
        "corr": [135.0, 135.0, 0.0, 0.0, 135.0, 135.0, 135.0, 0.0, 0.0, 135.0],
        "raw": [180.0] * 10,
        "as_ok": [True] * 10,
        "mag": [0] * 10,
        "agc": [40] * 10,
        "volt": [12.0] * 10,
        "amp": [0.1] * 10,
        "watt": [1.0] * 10,
        "ina_ok": [True] * 10,
        "map_ok": [True] * 10,
        "i2c_err": 0,
        "servo_ok": True,
        "mode": "lab",
        "out_mask": 0,
        "foot": {"ok": True, "seq": 1, "mask": 15, "force_kg": 0.4, "corners": {}},
        "foot_left": {"ok": True, "seq": 1, "mask": 15, "force_kg": 0.4, "corners": {}},
    }


def _v2_policy(t: float, *, running: bool) -> dict:
    """Policy order: slot 1 is logical axis 0 (right hip roll)."""
    obs = [0.0] * 38
    obs[1] = 0.05
    obs[12] = -1.0
    action = [0.0] * 10
    action_rad = [0.0] * 10
    cmd_rad = [0.0] * 10
    if running:
        action[1] = 2.0
        action_rad[1] = 0.5
        cmd_rad[1] = 0.35
    else:
        action = [None] * 10
        action_rad = [None] * 10
    return {
        "t": t,
        "seq": 10,
        "t_period_us": 33000,
        "t_sense_us": 1000,
        "t_policy_us": 800,
        "overrun": 0,
        "reason": 7,
        "reason_text": "upright-range",
        "safety": 2,
        "safety_text": "returning",
        "foot_bearing": False,
        "dist_ok": False,
        "joint_flag": [0] * 10,
        "age_ms": [0] * 12,
        "obs": obs,
        "action": action,
        "action_rad": action_rad,
        "cmd_rad": cmd_rad,
    }


def test_core_take_v2_maps_policy_onto_logical_axes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Policy slot 1 is the right hip roll, which the screen calls axis 0."""
    day = "2026-11-28"
    take_id = "005_121121"
    year, month, day_num = day.split("-")
    take = tmp_path / year / month / day_num / take_id
    (take / "sensors").mkdir(parents=True)
    (take / "policy").mkdir()
    (take / "commands").mkdir()
    (take / "events").mkdir()
    stamps = [1000.0, 1000.05, 1000.10]
    (take / "sensors" / "part-000.jsonl").write_text(
        "".join(json.dumps(_v2_sensor(t)) + "\n" for t in stamps),
        encoding="utf-8",
        newline="\n",
    )
    (take / "policy" / "part-000.jsonl").write_text(
        "".join(json.dumps(_v2_policy(t, running=index < 2)) + "\n" for index, t in enumerate(stamps)),
        encoding="utf-8",
        newline="\n",
    )
    (take / "commands" / "part-000.jsonl").write_text(
        json.dumps({"text": "POLICY", "enable": True, "vx": 0.0, "t": 1000.0}) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (take / "context.json").write_text(
        json.dumps(
            {
                "format_id": "core_take_v2",
                "project": {"learn_run": "stand_half", "checkpoint": "model_2200"},
                "policy": {"action_scale": 0.25, "envelope_rad": 0.35},
                "policy_joints": [
                    {"index": 0, "firmware_index": 5},
                    {"index": 1, "firmware_index": 0},
                    {"index": 2, "firmware_index": 6},
                    {"index": 3, "firmware_index": 1},
                    {"index": 4, "firmware_index": 7},
                    {"index": 5, "firmware_index": 2},
                    {"index": 6, "firmware_index": 8},
                    {"index": 7, "firmware_index": 3},
                    {"index": 8, "firmware_index": 9},
                    {"index": 9, "firmware_index": 4},
                ],
                "enums": {"reason": {"7": "upright-range"}, "safety": {"2": "returning"}},
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    (take / "meta.json").write_text(
        json.dumps(
            {
                "format_id": "core_take_v2",
                "take_id": take_id,
                "started_at": "2026-11-28T12:11:21+09:00",
                "started_unix": 1000.0,
                "recording": False,
                "sample_count": 3,
                "policy_count": 3,
                "stop_reason": "USB \u5207\u65ad",
                "duration_sec": 0.1,
                "open_parts": [],
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    client = _client(tmp_path, monkeypatch)
    listed = client.get("/api/lab/takes", params={"day": day})
    assert listed.status_code == 200
    meta = listed.json()["takes"][0]
    assert meta["supported"] is True
    assert meta["policy_count"] == 3

    base = f"/api/lab/takes/{day}/{take_id}"
    body = client.get(f"{base}/analysis").json()
    assert body["policy"]["samples"] == 3
    assert body["policy"]["action_rows"] == 2
    assert body["context"]["learn_run"] == "stand_half"
    assert body["context"]["checkpoint"] == "model_2200"
    assert body["context"]["policy_of_fw"][0] == 1
    assert body["context"]["envelope_rad"] == pytest.approx(0.35)
    assert _finding(body, "policy_reason:policy") is not None
    assert _finding(body, "policy_safety:policy") is not None
    assert _finding(body, "policy_clip:j0") is not None
    assert any(lane["id"] == "policy" for lane in body["health"]["lanes"])
    command = body["commands"][0]
    assert command["text"] == "POLICY"
    assert command["enable"] is True
    assert command["vx"] == pytest.approx(0.0)

    window = client.get(
        f"{base}/window",
        params={"channels": "p0.obs,j0.corr_rad,pol.reason,p0.clip", "from": 0, "to": 1},
    ).json()
    assert window["series"]["p0.obs"]["v"][0] == pytest.approx(0.05)
    assert window["series"]["j0.corr_rad"]["v"][0] == pytest.approx(0.0, abs=1e-9)
    assert window["series"]["pol.reason"]["v"][0] == pytest.approx(7)
    assert window["series"]["p0.clip"]["v"][0] == pytest.approx(0.15)
    # The third policy row did not run the network, so the clip is a gap.
    assert window["series"]["p0.clip"]["v"][2] is None

    sample = client.get(f"{base}/sample", params={"index": 0}).json()
    assert sample["policy"]["part"] == "policy/part-000.jsonl"
    assert sample["policy"]["row"]["obs"][1] == pytest.approx(0.05)


def _sim_policy(t: float, seq: int, *, big: bool, foot: bool, tilt: bool) -> dict:
    """One playback step. Wall-clock t is irregular; the period is 33333 us."""
    obs = [0.0] * 38
    obs[12] = -1.0
    if foot:
        obs[20] = 2.0
    if tilt:
        obs[14] = 2.5
    action_rad = [0.0] * 10
    if big:
        # Policy slot 1 is logical axis 0. Equal to cmd, so the robot clip
        # detector (the difference) must stay quiet.
        action_rad[1] = 0.8
    return {
        "t": t,
        "seq": seq,
        "t_period_us": 33333,
        "t_sense_us": 0,
        "t_policy_us": 0,
        "overrun": 0,
        "reason": 1,
        "safety": 0,
        "foot_bearing": foot,
        "dist_ok": True,
        "joint_flag": [0] * 10,
        "age_ms": [0] * 12,
        "obs": obs,
        "action": [value / 0.25 for value in action_rad],
        "action_rad": action_rad,
        "cmd_rad": list(action_rad),
    }


def test_sim_play_v1_uses_simulator_time_and_skips_sensor_faults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A playback has no meta.json and no sensors. The axis is t_period_us."""
    day = "2026-11-28"
    take_id = "001_132301"
    year, month, day_num = day.split("-")
    take = tmp_path / "sim" / year / month / day_num / take_id
    (take / "policy").mkdir(parents=True)
    # Wall gaps are 0.4 s and 0.15 s. Simulator steps stay 33.333 ms.
    rows = [
        _sim_policy(5000.0, 1, big=False, foot=False, tilt=False),
        _sim_policy(5000.4, 2, big=True, foot=True, tilt=True),
        _sim_policy(5000.55, 3, big=True, foot=False, tilt=False),
        _sim_policy(5000.9, 4, big=False, foot=False, tilt=False),
    ]
    (take / "policy" / "part-000.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    (take / "context.json").write_text(
        json.dumps(
            {
                "format_id": "sim_play_v1",
                "side": "sim",
                "experiment": "stand",
                "project": {"learn_run": "stand_half", "checkpoint": "model_2200", "task": "Play-v0"},
                "policy": {"action_scale": 0.25, "envelope_rad": 0.35},
                "policy_joints": [
                    {"index": 0, "firmware_index": 5, "name": "L hip roll"},
                    {"index": 1, "firmware_index": 0, "name": "R hip roll"},
                    {"index": 2, "firmware_index": 6},
                    {"index": 3, "firmware_index": 1},
                    {"index": 4, "firmware_index": 7},
                    {"index": 5, "firmware_index": 2},
                    {"index": 6, "firmware_index": 8},
                    {"index": 7, "firmware_index": 3},
                    {"index": 8, "firmware_index": 9},
                    {"index": 9, "firmware_index": 4},
                ],
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    client = _client(tmp_path, monkeypatch)
    listed = client.get("/api/lab/takes", params={"day": day})
    assert listed.status_code == 200
    meta = listed.json()["takes"][0]
    assert meta["supported"] is True
    assert meta["side"] == "sim"
    assert meta["format_id"] == "sim_play_v1"
    assert meta["name"] == "stand"
    assert meta["policy_count"] == 4
    assert meta["duration_sec"] == pytest.approx(3 * 33333 / 1_000_000, abs=1e-6)

    base = f"/api/lab/takes/{day}/{take_id}"
    body = client.get(f"{base}/analysis", params={"side": "sim"}).json()
    assert body["sample_count"] == 4
    assert body["duration_sec"] == pytest.approx(3 * 33333 / 1_000_000, abs=1e-4)
    assert body["context"]["experiment"] == "stand"
    assert body["context"]["task"] == "Play-v0"
    assert body["context"]["learn_run"] == "stand_half"
    assert body["joint_names"][0] == "R hip roll"
    assert body["policy"]["rate_hz"] == pytest.approx(30.0, abs=0.1)
    assert body["policy"]["clock"] == "sim"
    assert all(item["kind"] != "nodata" for item in body["findings"])
    assert _finding(body, "sim_envelope:j0") is not None
    assert _finding(body, "foot_saturated:foot") is not None
    assert _finding(body, "sim_tilt:policy") is not None
    assert _finding(body, "policy_clip:j0") is None

    window = client.get(
        f"{base}/window",
        params={"channels": "p0.action_rad,p0.obs", "from": 0, "to": 1, "side": "sim"},
    ).json()
    # Second sample is one simulator step later, not the 0.4 s wall gap.
    assert window["t"][1] == pytest.approx(0.0333, abs=0.001)
    assert window["t"][1] < 0.1
    assert window["series"]["p0.action_rad"]["v"][1] == pytest.approx(0.8)
    assert window["series"]["p0.action_rad"]["v"][0] == pytest.approx(0.0)


def test_sm105bl_is_not_a_missing_encoder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Knees and ankle pitch use servo feedback. mag 255 and a silent INA are normal."""
    day = "2026-11-28"
    take_id = "006_144630"
    year, month, day_num = day.split("-")
    take = tmp_path / year / month / day_num / take_id
    (take / "sensors").mkdir(parents=True)
    rows = []
    for index in range(3):
        as_ok = [True] * 10
        mag = [0] * 10
        corr = [135.0] * 10
        raw = [200.0] * 10
        amp = [0.1] * 10
        # Axis 1 is still an AS5600 and really failed.
        as_ok[1] = False
        mag[1] = 4
        corr[1] = None
        raw[1] = None
        # Axis 2 is an SM105BL with no present angle yet.
        as_ok[2] = False
        mag[2] = 255
        corr[2] = None
        raw[2] = None
        amp[2] = 0.0
        # Axis 3 is an SM105BL whose servo angle arrived. No magnet, no INA.
        as_ok[3] = True
        mag[3] = 255
        corr[3] = 1.0
        raw[3] = None
        amp[3] = 3.0
        rows.append(
            {
                "t": 1000.0 + index * 0.033,
                "seq": index,
                "as_ok": as_ok,
                "ina_ok": [True, True, False, False, True, True, True, True, True, True],
                "map_ok": [True, True, False, False, True, True, True, True, True, True],
                "mag": mag,
                "agc": [10 if code == 0 else 255 for code in mag],
                "corr": corr,
                "raw": raw,
                "cmd": [135.0, 135.0, 0.0, 0.0, 135.0, 135.0, 135.0, 0.0, 0.0, 135.0],
                "amp": amp,
                "volt": [12.0] * 10,
            }
        )
    (take / "sensors" / "part-000.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    joints = []
    for index, servo in enumerate(
        ["RDS51150", "RDS51150", "SM105BL", "SM105BL", "RDS51150", "RDS51150", "RDS51150", "SM105BL", "SM105BL", "RDS51150"]
    ):
        joints.append({"index": index, "name": f"j{index}", "servo": servo, "upright_deg": 0.0 if servo == "SM105BL" else 135.0})
    (take / "context.json").write_text(
        json.dumps({"format_id": "core_take_v2", "firmware_joints": joints}),
        encoding="utf-8",
        newline="\n",
    )
    (take / "meta.json").write_text(
        json.dumps({"format_id": "core_take_v2", "take_id": take_id, "started_unix": 1000.0, "sample_count": 3}),
        encoding="utf-8",
        newline="\n",
    )
    client = _client(tmp_path, monkeypatch)
    body = client.get(f"/api/lab/takes/{day}/{take_id}/analysis").json()
    assert body["context"]["servos"][2] == "SM105BL"
    assert body["context"]["servos"][0] == "RDS51150"
    assert _finding(body, "servo_fb:j2") is not None
    assert _finding(body, "dropout:j2") is None
    assert _finding(body, "dropout:j3") is None
    assert _finding(body, "magnet:j3") is None
    assert _finding(body, "no_map:j3") is None
    assert _finding(body, "overcurrent:j3") is None
    assert _finding(body, "undervolt:j3") is None
    # The hip pitch is still an encoder. A real AS5600 miss stays a dropout.
    assert _finding(body, "dropout:j1") is not None
    assert body["joint_stats"][3]["power"].get("amp_max") is None
