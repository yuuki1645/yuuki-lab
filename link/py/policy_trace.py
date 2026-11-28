#!/usr/bin/env python3
"""
方策の 1 周期を、実機とシミュで同じ形で残し、実験単位で比べる。

時刻を揃えた突き合わせはしない。同じ実験名の、有効な周期だけの
平均・ばらつき・欠測率・飛び率を出す。
波形は選んだ側の 1 本だけで、もう片方の同じ秒数とは重ねない。

実機のファイルは本記録フォルダの policy_trace.jsonl。
シミュの再生は storage.yaml の sim/ 以下（形式 sim_play_v1）。
storage.yaml が無いときと、以前の再生は atom-rt/data/policy_traces/sim/。
画面はどちらもローカル側だけを読む。NAS の写しは見ない。
"""

from __future__ import annotations

import json
import math
import re
import threading
from pathlib import Path
from typing import Any, Iterator

FORMAT_ID = "policy_trace_v1"
# 足裏 8 個。合計がこれ未満の周期は、吊っていて体重を受けていないとみなす。
FOOT_DIMS = range(16, 24)
# この文字だけをフォルダ名に使う。
_ID_OK = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

# 学習の PolicyCfg と同じ順。画面の度にはしない。
DIMS: list[dict[str, str]] = [
    {"key": "left_hip_roll", "label": "左股ロール", "group": "joint"},
    {"key": "right_hip_roll", "label": "右股ロール", "group": "joint"},
    {"key": "left_hip_pitch", "label": "左股ピッチ", "group": "joint"},
    {"key": "right_hip_pitch", "label": "右股ピッチ", "group": "joint"},
    {"key": "left_knee_pitch", "label": "左ひざ", "group": "joint"},
    {"key": "right_knee_pitch", "label": "右ひざ", "group": "joint"},
    {"key": "left_ankle_pitch", "label": "左かかとピッチ", "group": "joint"},
    {"key": "right_ankle_pitch", "label": "右かかとピッチ", "group": "joint"},
    {"key": "left_ankle_roll", "label": "左かかとロール", "group": "joint"},
    {"key": "right_ankle_roll", "label": "右かかとロール", "group": "joint"},
    {"key": "gravity_x", "label": "重力 x", "group": "imu"},
    {"key": "gravity_y", "label": "重力 y", "group": "imu"},
    {"key": "gravity_z", "label": "重力 z", "group": "imu"},
    {"key": "gyro_x", "label": "角速度 x", "group": "imu"},
    {"key": "gyro_y", "label": "角速度 y", "group": "imu"},
    {"key": "gyro_z", "label": "角速度 z", "group": "imu"},
    {"key": "foot_l_tl", "label": "左足 つま先左", "group": "foot"},
    {"key": "foot_l_tr", "label": "左足 つま先右", "group": "foot"},
    {"key": "foot_l_bl", "label": "左足 かかと左", "group": "foot"},
    {"key": "foot_l_br", "label": "左足 かかと右", "group": "foot"},
    {"key": "foot_r_tl", "label": "右足 つま先左", "group": "foot"},
    {"key": "foot_r_tr", "label": "右足 つま先右", "group": "foot"},
    {"key": "foot_r_bl", "label": "右足 かかと左", "group": "foot"},
    {"key": "foot_r_br", "label": "右足 かかと右", "group": "foot"},
    {"key": "phase_sin", "label": "位相 sin", "group": "phase"},
    {"key": "phase_cos", "label": "位相 cos", "group": "phase"},
    {"key": "vx", "label": "前進指令", "group": "command"},
    {"key": "yaw", "label": "ヨー指令", "group": "command"},
    {"key": "action_0", "label": "直前出力 左股ロール", "group": "action"},
    {"key": "action_1", "label": "直前出力 右股ロール", "group": "action"},
    {"key": "action_2", "label": "直前出力 左股ピッチ", "group": "action"},
    {"key": "action_3", "label": "直前出力 右股ピッチ", "group": "action"},
    {"key": "action_4", "label": "直前出力 左ひざ", "group": "action"},
    {"key": "action_5", "label": "直前出力 右ひざ", "group": "action"},
    {"key": "action_6", "label": "直前出力 左かかとピッチ", "group": "action"},
    {"key": "action_7", "label": "直前出力 右かかとピッチ", "group": "action"},
    {"key": "action_8", "label": "直前出力 左かかとロール", "group": "action"},
    {"key": "action_9", "label": "直前出力 右かかとロール", "group": "action"},
]

EXPERIMENTS = ("直立", "1関節", "体重移動", "浅いしゃがみ")


def repo_root() -> Path:
    """link/py からリポジトリ直下。"""
    return Path(__file__).resolve().parents[2]


def recordings_root() -> Path:
    return repo_root() / "atom-rt" / "data" / "recordings"


def sim_root() -> Path:
    path = repo_root() / "atom-rt" / "data" / "policy_traces" / "sim"
    path.mkdir(parents=True, exist_ok=True)
    return path


def next_name_path() -> Path:
    return repo_root() / "atom-rt" / "data" / "policy_traces" / "next_name.txt"


def read_next_name() -> str:
    """再生が次に付ける実験名。無ければ直立。"""
    path = next_name_path()
    if not path.is_file():
        return EXPERIMENTS[0]
    text = path.read_text(encoding="utf-8").strip()
    return text or EXPERIMENTS[0]


def write_next_name(name: str) -> str:
    """再生側が読む実験名。空なら直立。"""
    label = (name or "").strip() or EXPERIMENTS[0]
    path = next_name_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(label + "\n", encoding="utf-8")
    return label


def _safe_id(value: str) -> str | None:
    if _ID_OK.match(value or ""):
        return value
    return None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _mean_std(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, math.sqrt(var)


def iter_rows(path: Path) -> Iterator[dict[str, Any]]:
    """壊れた末尾の 1 行は読み飛ばす。記録中のファイルを見ても落ちない。"""
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get("obs"), list):
                yield row


def iter_source(path: Path) -> Iterator[dict[str, Any]]:
    """1 本の jsonl か、再生 take の policy/part-*.jsonl を番号順に読む。"""
    if path.is_dir():
        policy = path / "policy"
        if not policy.is_dir():
            return
        for part in sorted(policy.glob("part-*.jsonl")):
            yield from iter_rows(part)
        return
    yield from iter_rows(path)


def _trace_path_real(rec_id: str) -> Path | None:
    safe = _safe_id(rec_id)
    if safe is None:
        return None
    path = recordings_root() / safe / "policy_trace.jsonl"
    return path if path.is_file() else None


def _trace_path_sim(rec_id: str) -> Path | None:
    """以前の 1 ファイルか、sim_play_v1 の take フォルダ。保管先の NAS は見ない。"""
    safe = _safe_id(rec_id)
    if safe is None:
        return None
    legacy = sim_root() / safe / "policy_trace.jsonl"
    if legacy.is_file():
        return legacy
    from sim_play_log import find_play_take

    return find_play_take(safe)


def _meta_of(folder: Path, side: str) -> dict[str, Any] | None:
    meta_path = folder / "meta.json"
    trace = folder / "policy_trace.jsonl"
    if not trace.is_file():
        return None
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                meta = loaded
        except (OSError, json.JSONDecodeError):
            meta = {}
    # 実機は本記録の sample_count がテレメトリの点数なので、方策の行数を優先する。
    count = int(meta.get("policy_trace_count") or 0)
    if count <= 0 and meta.get("side") == "sim":
        count = int(meta.get("sample_count") or 0)
    if count <= 0:
        # 記録中は meta が遅れる。行数はファイルを数える。
        count = sum(1 for _ in iter_rows(trace))
    if count <= 0:
        return None
    return {
        "id": str(meta.get("id") or folder.name),
        "name": str(meta.get("name") or folder.name),
        "side": side,
        "sample_count": count,
        "started_at": meta.get("started_at") or "",
    }


def list_traces() -> dict[str, Any]:
    """実機は本記録。シミュはローカルの sim_play_v1 と、以前の 1 ファイル。新しい順。"""
    real: list[dict[str, Any]] = []
    root = recordings_root()
    if root.is_dir():
        for folder in root.iterdir():
            if not folder.is_dir():
                continue
            row = _meta_of(folder, "real")
            if row is not None:
                real.append(row)
    sim: list[dict[str, Any]] = []
    seen: set[str] = set()
    legacy_root = sim_root()
    if legacy_root.is_dir():
        for folder in legacy_root.iterdir():
            if not folder.is_dir() or not (folder / "policy_trace.jsonl").is_file():
                continue
            row = _meta_of(folder, "sim")
            if row is None or row["id"] in seen:
                continue
            seen.add(row["id"])
            sim.append(row)
    from sim_play_log import list_play_takes

    for row in list_play_takes():
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        sim.append(row)
    real.sort(key=lambda item: str(item.get("started_at") or item["id"]), reverse=True)
    sim.sort(key=lambda item: str(item.get("started_at") or item["id"]), reverse=True)
    return {"real": real, "sim": sim, "next_name": read_next_name(), "experiments": list(EXPERIMENTS)}


def _path_for(side: str, rec_id: str) -> Path | None:
    if side == "real":
        return _trace_path_real(rec_id)
    if side == "sim":
        return _trace_path_sim(rec_id)
    return None


def _timing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """実機の計測の質。シミュの波形と重ねるためではない。"""
    periods = [int(r["t_period_us"]) for r in rows if isinstance(r.get("t_period_us"), int)]
    overruns = [1 for r in rows if int(r.get("overrun") or 0) != 0]
    ages: list[int] = []
    for row in rows:
        raw = row.get("age_ms")
        if not isinstance(raw, list):
            continue
        for value in raw:
            if isinstance(value, int) and 0 <= value < 65535:
                ages.append(value)
    periods.sort()
    ages.sort()

    def mid(values: list[int]) -> int | None:
        if not values:
            return None
        return values[len(values) // 2]

    safety = sum(1 for r in rows if int(r.get("safety") or 0) != 0)
    return {
        "rows": len(rows),
        "period_us_median": mid(periods),
        "overrun_rate": (len(overruns) / len(rows)) if rows else None,
        "age_ms_median": mid(ages),
        "safety_rate": (safety / len(rows)) if rows else None,
    }


def _dim_flag(row: dict[str, Any], index: int) -> int:
    """0 有効、1 欠測、2 飛び、3 揺れ。センサが無い欄は 0。"""
    if index < 10:
        flags = row.get("joint_flag")
        if isinstance(flags, list) and index < len(flags) and isinstance(flags[index], int):
            return int(flags[index])
        return 1
    if 10 <= index <= 15:
        # 重力も角速度も、IMU が無ければまとめて欠測。
        obs = row.get("obs")
        if isinstance(obs, list) and len(obs) > 12 and obs[10] is None and obs[11] is None and obs[12] is None:
            return 1
    return 0


def summarize_file(path: Path) -> dict[str, Any]:
    """1 本の記録。平均は有効な値だけ。欠測率は全周期に対する割合。"""
    rows = list(iter_source(path))
    dims: list[dict[str, Any]] = []
    for index, spec in enumerate(DIMS):
        values: list[float] = []
        missing = 0
        jump = 0
        shake = 0
        skipped_safety = 0
        skipped_foot = 0
        for row in rows:
            flag = _dim_flag(row, index)
            if flag == 1:
                missing += 1
                continue
            if flag == 2:
                jump += 1
                continue
            if flag == 3:
                shake += 1
                continue
            # 安全が働いた周期は、どの量の平均からも外す。欠測は上で率に入っている。
            if int(row.get("safety") or 0) != 0:
                skipped_safety += 1
                continue
            if index in FOOT_DIMS and not row.get("foot_bearing"):
                skipped_foot += 1
                continue
            obs = row.get("obs")
            if not isinstance(obs, list) or index >= len(obs):
                missing += 1
                continue
            number = _finite(obs[index])
            if number is None:
                missing += 1
                continue
            values.append(number)
        mean, std = _mean_std(values)
        total = len(rows)
        dims.append(
            {
                "index": index,
                "key": spec["key"],
                "label": spec["label"],
                "group": spec["group"],
                "mean": mean,
                "std": std,
                "n": len(values),
                "missing_rate": (missing / total) if total else None,
                "jump_rate": (jump / total) if total else None,
                "shake_rate": (shake / total) if total else None,
                "safety_skip": skipped_safety,
                "foot_skip": skipped_foot,
            }
        )
    return {"rows": len(rows), "dims": dims, "timing": _timing(rows)}


def series_file(path: Path, index: int, limit: int = 900) -> dict[str, Any]:
    """1 本の時間順。横軸はその記録の中の経過秒。欠測と飛びは値を出さない。"""
    if index < 0 or index >= len(DIMS):
        return {"ok": False, "error": "dim"}
    rows = list(iter_source(path))
    stride = max(1, math.ceil(len(rows) / limit)) if rows else 1
    points: list[dict[str, Any]] = []
    elapsed_us = 0
    for i, row in enumerate(rows):
        period = row.get("t_period_us")
        elapsed_us += int(period) if isinstance(period, int) and period > 0 else 33333
        if i % stride != 0:
            continue
        flag = _dim_flag(row, index)
        obs = row.get("obs")
        value = None
        if flag == 0 and isinstance(obs, list) and index < len(obs):
            value = _finite(obs[index])
        points.append(
            {
                "t": elapsed_us / 1.0e6,
                "v": value,
                "flag": flag,
                "safety": int(row.get("safety") or 0),
            }
        )
    spec = DIMS[index]
    return {
        "ok": True,
        "index": index,
        "label": spec["label"],
        "key": spec["key"],
        "stride": stride,
        "points": points,
    }


def register_routes(app: Any) -> None:
    """実機の橋とシミュの橋の両方に、同じ読み取り API を足す。"""
    from flask import jsonify, request

    @app.get("/api/policy-trace/list")
    def policy_trace_list():
        body = list_traces()
        body["ok"] = True
        return jsonify(body)

    @app.post("/api/policy-trace/sim-name")
    def policy_trace_sim_name():
        payload = request.get_json(silent=True) or {}
        name = write_next_name(str(payload.get("name") or ""))
        return jsonify({"ok": True, "name": name})

    @app.get("/api/policy-trace/summary")
    def policy_trace_summary():
        real_id = str(request.args.get("real") or "")
        sim_id = str(request.args.get("sim") or "")
        real_path = _path_for("real", real_id)
        sim_path = _path_for("sim", sim_id)
        if real_path is None or sim_path is None:
            return jsonify({"ok": False, "error": "記録が見つかりません"}), 404
        return jsonify(
            {
                "ok": True,
                "real": summarize_file(real_path),
                "sim": summarize_file(sim_path),
                "dims": [{"index": i, "label": spec["label"], "group": spec["group"]} for i, spec in enumerate(DIMS)],
            }
        )

    @app.get("/api/policy-trace/series")
    def policy_trace_series():
        side = str(request.args.get("side") or "")
        rec_id = str(request.args.get("id") or "")
        try:
            index = int(request.args.get("dim") or 0)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "dim"}), 400
        path = _path_for(side, rec_id)
        if path is None:
            return jsonify({"ok": False, "error": "記録が見つかりません"}), 404
        body = series_file(path, index)
        if not body.get("ok"):
            return jsonify(body), 400
        return jsonify(body)


_sim_log: Any = None
_sim_lock = threading.Lock()


def sim_log() -> Any:
    """再生プロセスの中で 1 つ。ローカルへ書き、閉じた断片を NAS へ送る。"""
    global _sim_log
    with _sim_lock:
        if _sim_log is None:
            from sim_play_log import shared_sim_log

            _sim_log = shared_sim_log()
        return _sim_log
