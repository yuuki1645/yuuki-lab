# app.py
from __future__ import annotations

import json
import os
from typing import Any, Dict

from flask import Flask, render_template, request, jsonify

from servo import move_servo_logical, move_servo_physical, SERVO_MAP, PHYSICAL_MIN, PHYSICAL_MAX
from kinematics import KINEMATICS

app = Flask(__name__)

STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")

# state.json 形式（自動生成）
# {
#   "last_mode": "logical" | "physical",
#   "servos": {
#     "R_KNEE": {"logical": 10, "physical": 70},
#     ...
#   }
# }

def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_PATH):
        return {"last_mode": "logical", "servos": {}}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if "last_mode" not in data:
            data["last_mode"] = "logical"
        if "servos" not in data or not isinstance(data["servos"], dict):
            data["servos"] = {}
        return data
    except Exception as e:
        print("[WARN] failed to load state.json:", e)
        return {"last_mode": "logical", "servos": {}}

def save_state(state: Dict[str, Any]) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[WARN] failed to save state.json:", e)

def default_logical(servo_name: str) -> float:
    kin = KINEMATICS[servo_name]
    return round((kin.logical_range.lo + kin.logical_range.hi) / 2)

def default_physical(_: str) -> float:
    return 135.0

@app.get("/")
def index():
    state = load_state()
    last_mode = state.get("last_mode", "logical")
    per_servo = state.get("servos", {})

    servos = []
    for name in SERVO_MAP.keys():
        kin = KINEMATICS[name]
        entry = per_servo.get(name, {}) if isinstance(per_servo.get(name, {}), dict) else {}

        last_logical = entry.get("logical", default_logical(name))
        last_physical = entry.get("physical", default_physical(name))

        # clamp
        last_logical = max(kin.logical_range.lo, min(kin.logical_range.hi, float(last_logical)))
        last_physical = max(PHYSICAL_MIN, min(PHYSICAL_MAX, float(last_physical)))

        servos.append({
            "name": name,
            "logical_lo": kin.logical_range.lo,
            "logical_hi": kin.logical_range.hi,
            "last_logical": last_logical,
            "last_physical": last_physical,
        })

    return render_template(
        "index.html",
        servos=servos,
        last_mode=last_mode,
        physical_min=PHYSICAL_MIN,
        physical_max=PHYSICAL_MAX,
    )

@app.post("/api/move")
def api_move():
    data = request.json or {}
    servo = data["servo"]
    mode = data.get("mode", "logical")
    angle = float(data["angle"])

    if mode == "physical":
        result = move_servo_physical(servo, angle)
    else:
        mode = "logical"
        result = move_servo_logical(servo, angle)

    # 保存
    state = load_state()
    state["last_mode"] = mode
    state.setdefault("servos", {})
    state["servos"].setdefault(servo, {})

    if mode == "physical":
        state["servos"][servo]["physical"] = angle
    else:
        state["servos"][servo]["logical"] = angle
        # logical → physical の結果が返っていれば保存しておく（次回の物理モード初期値にも使える）
        if isinstance(result, dict) and "physical" in result:
            state["servos"][servo]["physical"] = float(result["physical"])

    save_state(state)

    return jsonify({"status": "ok", "mode": mode, **result})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
