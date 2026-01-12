# app.py
from __future__ import annotations

from typing import Any, Dict

import requests
from flask import Flask, render_template, request, jsonify
from utils import clamp
from pprint import pprint

app = Flask(__name__)

SERVO_DAEMON_URL = "http://localhost:5000"

# サーボ名 -> チャンネル番号のマッピング（servo_daemon/app.py と一致させる）
SERVO_NAME_TO_CH = {
    "R_HIP1": 0,
    "R_HIP2": 1,
    "R_KNEE": 2,
    "R_HEEL": 3,
    "L_HIP1": 8,
    "L_HIP2": 9,
    "L_KNEE": 10,
    "L_HEEL": 11,
}

def get_servo_daemon_state() -> Dict[str, Any]:
    """servo_daemonから状態を取得する"""
    try:
        response = requests.get(f"{SERVO_DAEMON_URL}/state", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print("[WARN] failed to get servo daemon state:", e)
    return {}

def get_servo_info() -> Dict[str, Any]:
    """servo_daemonからサーボ情報を取得する"""
    try:
        response = requests.get(f"{SERVO_DAEMON_URL}/servos", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print("[WARN] failed to get servo info from servo_daemon:", e)
    return {"servos": []}

@app.get("/")
def index():
    # servo_daemon から最新の状態を取得
    servo_info = get_servo_info()
    daemon_state = get_servo_daemon_state()

    # サーボ情報から論理角レンジなどを取得
    servos_data = servo_info.get("servos", [])

    servos = []
    for servo_data in servos_data:
        name = servo_data["name"]
        ch = servo_data["ch"]
        ch_str = str(ch)

        # servo_daemon の状態から取得（チャンネル番号をキーとする）
        daemon_entry = daemon_state.get(ch_str, {})
        if isinstance(daemon_entry, dict):
            last_logical = daemon_entry.get("logical")
            last_physical = daemon_entry.get("physical")
        else:
            last_logical = None
            last_physical = None

        # デフォルト値の設定
        logical_lo = servo_data["logical_lo"]
        logical_hi = servo_data["logical_hi"]

        # servo_daemonから取得したデフォルト値を仕様
        default_logical = servo_data.get("default_logical")
        default_physical = servo_data.get("default_physical")

        if last_logical is None:
            last_logical = default_logical
        if last_physical is None:
            last_physical = default_physical

        # clamp
        last_logical = clamp(float(last_logical), logical_lo, logical_hi)

        # サーボごとの物理角範囲を取得
        servo_physical_min = servo_data.get("physical_min")
        servo_physical_max = servo_data.get("physical_max")
        last_physical = clamp(float(last_physical), servo_physical_min, servo_physical_max)

        servos.append({
            "name": name,
            "logical_lo": logical_lo,
            "logical_hi": logical_hi,
            "physical_min": servo_physical_min,
            "physical_max": servo_physical_max,
            "last_logical": last_logical,
            "last_physical": last_physical,
        })

    return render_template(
        "index.html",
        servos=servos,
        last_mode="logical"
    )

@app.post("/api/move")
def api_move():
    data = request.json or {}
    servo_name = data["servo"]
    mode = data.get("mode", "logical")
    angle = float(data["angle"])

    # サーボ名からチャンネル番号を取得
    if servo_name not in SERVO_NAME_TO_CH:
        return jsonify({"status": "error", "message": f"Unknown servo: {servo_name}"}), 400

    ch = SERVO_NAME_TO_CH[servo_name]

    # ログ出力（リクエストパラメータを表示）
    print(f"[API] POST /api/move - servo={servo_name}({ch}), mode={mode}, angle={angle}")

    # servo_daemon のAPIを呼び出す
    try:
        if mode == "physical":
            url = f"{SERVO_DAEMON_URL}/set_physical"
            params = {"ch": ch, "p_ang": angle}
        else:
            mode = "logical"
            url = f"{SERVO_DAEMON_URL}/set_logical"
            params = {"ch": ch, "l_ang": angle}

        response = requests.get(url, params=params, timeout=5)
        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": f"servo_daemon returned {response.status_code}"
            }), 500

        # レスポンスから全状態情報を取得
        response_data = response.json()

        result = {
            "status": "ok",
            "mode": mode,
            "servo": servo_name,
        }

        # 全状態情報を含める
        if "state" in response_data:
            result["state"] = response_data["state"]

        return jsonify(result)

    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "message": f"Network error: {str(e)}"
        }), 500
        

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
