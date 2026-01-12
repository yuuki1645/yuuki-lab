# app.py
from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from flask import Flask, render_template, request, jsonify
from utils import clamp
import threading

app = Flask(__name__)

SERVO_DAEMON_URL = "http://127.0.0.1:5000"

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

# ===== エラーハンドリング統一のヘルパー関数 =====
def api_get(endpoint: str, timeout: float = 5.0, **kwargs) -> Optional[Dict[str, Any]]:
    """
    servo_daemonへのGETリクエストを統一処理
    
    Args:
        endpoint: APIエンドポイント（例: "/state", "/servos"）
        timeout: タイムアウト時間（秒）
        **kwargs: requests.get()に渡す追加パラメータ
    
    Returns:
        成功時: JSONレスポンスの辞書、失敗時: None
    """
    try:
        url = f"{SERVO_DAEMON_URL}{endpoint}"
        response = requests.get(url, timeout=timeout, **kwargs)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[WARn] API call failed ({endpoint}): status={response.status_code}")
    except requests.exceptions.Timeout:
        print(f"[WARN] API call timed out ({endpoint})")
    except requests.exceptions.ConnectionError:
        print(f"[WARN] API connection error ({endpoint})")
    except Exception as e:
        print(f"[WARN] API call failed ({endpoint}): {e}")
    return None

def api_post(endpoint: str, timeout: float = 1.0, **kwargs) -> bool:
    """
    servo_daemonへのPOSTリクエストを統一処理（fire-and-forget用）
    
    Args:
        endpoint: APIエンドポイント（例: "/set"）
        timeout: タイムアウト時間（秒）
        **kwargs: requests.post()に渡す追加パラメータ（json, paramsなど）
    
    Returns:
        成功時: True、失敗時: False（ログは自動出力）
    """
    try:
        url = f"{SERVO_DAEMON_URL}{endpoint}"
        response = requests.post(url, timeout=timeout, **kwargs)
        return response.status_code == 200
    except requests.exceptions.Timeout:
        print(f"[WARN] API call timeout ({endpoint})")
    except requests.exceptions.ConnectionError:
        print(f"[WARN] API connection error ({endpoint})")
    except Exception as e:
        print(f"[WARN] API call error ({endpoint}): {e}")
    return False

def get_servo_daemon_state() -> Dict[str, Any]:
    """servo_daemonから状態を取得する"""
    result = api_get("/state")
    return result if result is not None else {}

def get_servo_info() -> Dict[str, Any]:
    """servo_daemonからサーボ情報を取得する"""
    result = api_get("/servos")
    return result if result is not None else {"servos": []}

@app.get("/")
def index():
    # 1回のAPI呼び出しで完結
    servo_info = get_servo_info()
    servos_data = servo_info.get("servos", [])

    servos = []
    for servo_data in servos_data:
        # 状態情報は既にservo_dataに含まれている
        last_logical = servo_data.get("last_logical") or servo_data.get("default_logical")
        last_physical = servo_data.get("last_physical") or servo_data.get("default_physical")

        # clamp
        last_logical = clamp(float(last_logical), servo_data["logical_lo"], servo_data["logical_hi"])
        last_physical = clamp(float(last_physical), servo_data["physical_min"], servo_data["physical_max"])

        servos.append({
            "name": servo_data["name"],
            "logical_lo": servo_data["logical_lo"],
            "logical_hi": servo_data["logical_hi"],
            "physical_min": servo_data["physical_min"],
            "physical_max": servo_data["physical_max"],
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

    # 非同期でリクエストを送信（レスポンスを待たない）
    def send_request():
        # 統合されたエンドポイントを使用（シンプル！）
        api_post("/set", timeout=1, json={
            "ch": ch,
            "mode": mode,
            "angle": angle
        })

    # バックグラウンドで実行
    thread = threading.Thread(target=send_request)
    thread.daemon = True
    thread.start()

    # 即座に成功を返す
    return jsonify({
        "status": "ok",
        "mode": mode,
        "servo": servo_name,
    })
        

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
