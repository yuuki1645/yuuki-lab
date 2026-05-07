# type: ignore

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from servo import SERVO_MAP, move_servo_logical, move_servo_physical, move_servos_logical, move_servos_physical
from kinematics import KINEMATICS
from state_manager import StateManager
from imu import Mpu6050Reader
import argparse
import logging
import time
import threading

app = Flask(__name__)
CORS(app)  # すべてのオリジンからのアクセスを許可
socketio = SocketIO(app, cors_allowed_origins="*")

# 状態管理インスタンスを作成
state_manager = StateManager(state_path="./state.json")
imu_reader = Mpu6050Reader()

imu_stream_rate_hz = 30.0
imu_stream_enabled = False
imu_stream_task_started = False
imu_stream_lock = threading.Lock()

SERVO_CH_2_NAME = {
	0: "R_HIP1",
	1: "R_HIP2",
	2: "R_KNEE",
	3: "R_HEEL",
	4: "R_HEEL_ROLL",
	8: "L_HIP1",
	9: "L_HIP2",
	10: "L_KNEE",
	11: "L_HEEL",
	12: "L_HEEL_ROLL",
}


def _parse_transition_payload(data: dict):
	"""遷移API/WSで共通利用する入力パース"""
	mode = data.get("mode", "logical")
	angles = data.get("angles", {})
	duration = float(data.get("duration", 3.0))
	angles_dict = {int(ch_str): float(angle) for ch_str, angle in angles.items()}
	return mode, angles_dict, duration


def _emit_imu_status():
	emit(
		"imu/status",
		{
			"streaming": imu_stream_enabled,
			"rate_hz": imu_stream_rate_hz,
			"sensor": imu_reader.status(),
		},
	)


def _emit_imu_error(code: str, message: str, detail: str | None = None):
	payload = {
		"ok": False,
		"error_code": code,
		"message": message,
	}
	if detail:
		payload["detail"] = detail
	socketio.emit("imu/error", payload)


def _imu_stream_loop():
	"""IMU値を定期取得して全クライアントへ配信する。"""
	global imu_stream_enabled
	while True:
		with imu_stream_lock:
			streaming = imu_stream_enabled
			rate_hz = imu_stream_rate_hz

		interval = 1.0 / max(1.0, float(rate_hz))
		if not streaming:
			socketio.sleep(0.2)
			continue

		try:
			sample = imu_reader.sample()
			socketio.emit("imu/sample", sample)
		except Exception as e:
			err = imu_reader.get_error_info()
			_emit_imu_error(
				err["code"],
				"MPU6050 の読み取りに失敗しました。配信を停止します。",
				str(e),
			)
			with imu_stream_lock:
				imu_stream_enabled = False
			socketio.emit(
				"imu/status",
				{
					"streaming": False,
					"rate_hz": rate_hz,
					"sensor": imu_reader.status(),
				},
			)

		socketio.sleep(interval)


def _ensure_imu_task_started():
	global imu_stream_task_started
	if imu_stream_task_started:
		return
	imu_stream_task_started = True
	socketio.start_background_task(_imu_stream_loop)


def _start_transition_internal(angles_dict: dict[int, float], mode: str, duration: float):
	"""現在角度から目標角度への遷移をバックグラウンド開始する"""
	# 現在の角度を取得
	state = state_manager.get_all()

	# 各サーボの現在角度と目標角度を計算
	transitions = {}
	for ch, target_angle in angles_dict.items():
		if ch not in SERVO_CH_2_NAME:
			continue

		servo_state = state.get(str(ch), {})
		current_angle = float(servo_state.get(mode, 0))
		target_angle_float = float(target_angle)

		transitions[ch] = {
			"current": current_angle,
			"target": target_angle_float,
			"servo_name": SERVO_CH_2_NAME[ch]
		}

	def execute_transition():
		steps = max(30, int(duration * 10))  # 10Hz更新、最低30ステップ
		step_delay = duration / steps

		for step in range(steps + 1):
			progress = step / steps

			# 各ステップで全サーボの補間角度を計算
			interpolated_angles = {}
			for ch, trans in transitions.items():
				current = trans["current"]
				target = trans["target"]
				# 線形補間
				interpolated_angles[ch] = current + (target - current) * progress

			# 一括でサーボを動かす
			try:
				_set_servos_angles_internal(interpolated_angles, mode)
			except Exception as e:
				print(f"[SERVO] ERROR during transition: {e}")

			if step < steps:
				time.sleep(step_delay)

	thread = threading.Thread(target=execute_transition)
	thread.daemon = True
	thread.start()
	return len(transitions)


def _servos_list_payload() -> dict:
	"""全サーボのメタ情報と現在状態（旧 GET /servos と同形）。"""
	state = state_manager.get_all()
	servos = []
	for name, ch in SERVO_MAP.items():
		kin = KINEMATICS[name]
		ch_str = str(ch)
		servo_state = state.get(ch_str, {})
		servos.append({
			"name": name,
			"ch": ch,
			"logical_lo": kin.logical_range.lo,
			"logical_hi": kin.logical_range.hi,
			"physical_min": kin.physical_range.lo,
			"physical_max": kin.physical_range.hi,
			"default_logical": kin.default_logical,
			"default_physical": kin.default_physical,
			"last_logical": servo_state.get("logical"),
			"last_physical": servo_state.get("physical"),
		})
	return {"servos": servos}


def _set_servo_angle_internal(ch: int, angle: float, mode: str):
	"""サーボ角度を設定する内部処理（レスポンスを返さない）"""
	if mode == "logical":
		result = move_servo_logical(SERVO_CH_2_NAME[ch], angle)
	else:
		result = move_servo_physical(SERVO_CH_2_NAME[ch], angle)

	state_manager.set(str(ch), {
		"logical": result["logical"],
		"physical": result["physical"]
	})

	# 結果をログに出力
	servo_name = SERVO_CH_2_NAME[ch]
	print(f"[SERVO] SUCCESS - {servo_name} (ch={ch}): logical={result['logical']:.1f}, physical={result['physical']:.1f}")
	
	return result

def _set_servos_angles_internal(angles_dict: dict, mode: str):
	"""
	複数のサーボ角度を一括で設定する内部処理
	
	Args:
		angles_dict: {ch: angle} の形式（chはint、angleはfloat）
		mode: "logical" または "physical"
	
	Returns:
		{"success": [...], "errors": [...]} の形式
	"""
	results = {"success": [], "errors": []}
	
	# チャンネル番号からサーボ名への変換
	servo_angles = {}
	for ch, angle in angles_dict.items():
		if ch not in SERVO_CH_2_NAME:
			results["errors"].append({
				"ch": ch,
				"message": f"Unknown channel: {ch}"
			})
			continue
		servo_name = SERVO_CH_2_NAME[ch]
		servo_angles[servo_name] = float(angle)
	
	if not servo_angles:
		return results
	
	# 一括でサーボを動かす
	try:
		if mode == "logical":
			servo_results = move_servos_logical(servo_angles)
		else:
			servo_results = move_servos_physical(servo_angles)
		
		# 状態を一括更新
		state_updates = {}
		success_logs = []  # ログを集めるリスト
		
		for servo_name, result in servo_results.items():
			ch = result["ch"]
			state_updates[str(ch)] = {
				"logical": result["logical"],
				"physical": result["physical"]
			}
			
			# ログ情報をリストに追加
			success_logs.append(f"{servo_name}: l={result['logical']:.1f}")
			
			results["success"].append({
				"ch": ch,
				"servo_name": servo_name,
				"logical": result["logical"],
				"physical": result["physical"]
			})
		
		# 全てのサーボ情報を1行にまとめて出力
		if success_logs:
			# print(f"[SERVO] SUCCESS - {', '.join(success_logs)}")
			pass
		
		# 状態を一括更新
		for ch_str, state_data in state_updates.items():
			state_manager.set(ch_str, state_data)
			
	except Exception as e:
		print(f"[SERVO] ERROR during batch operation: {e}")
		# エラーが発生した場合、各サーボを個別に試行
		for ch, angle in angles_dict.items():
			if ch not in SERVO_CH_2_NAME:
				continue
			try:
				_set_servo_angle_internal(ch, angle, mode)
				results["success"].append({"ch": ch, "status": "ok"})
			except Exception as e2:
				servo_name = SERVO_CH_2_NAME.get(ch, f"ch{ch}")
				results["errors"].append({
					"ch": ch,
					"servo_name": servo_name,
					"message": str(e2)
				})
	
	return results


@socketio.on("connect")
def ws_connect():
	emit("connection/status", {"status": "connected"})
	emit("servo/list", _servos_list_payload())
	_emit_imu_status()


@socketio.on("disconnect")
def ws_disconnect():
	print("[WS] client disconnected")


@socketio.on("servo/list")
def ws_servo_list(_data=None):
	"""旧 GET /servos と同等の一覧を返す。"""
	try:
		emit("servo/list", _servos_list_payload())
	except Exception as e:
		emit("error", {"status": "error", "message": str(e)})


@socketio.on("servo/set")
def ws_set_servo(data):
	try:
		ch = int(data.get("ch"))
		mode = data.get("mode", "logical")
		angle = float(data.get("angle"))
		result = _set_servo_angle_internal(ch, angle, mode)
		emit("servo/result", {"status": "ok", "result": result})
	except Exception as e:
		emit("error", {"status": "error", "message": str(e)})


@socketio.on("servo/set_multiple")
def ws_set_multiple(data):
	try:
		mode = data.get("mode", "logical")
		angles = data.get("angles", {})
		angles_dict = {int(ch_str): float(angle) for ch_str, angle in angles.items()}
		results = _set_servos_angles_internal(angles_dict, mode)
		emit("servo/result_multiple", {"status": "ok", "results": results})
	except Exception as e:
		emit("error", {"status": "error", "message": str(e)})


@socketio.on("servo/transition")
def ws_transition(data):
	try:
		mode, angles_dict, duration = _parse_transition_payload(data or {})
		transition_count = _start_transition_internal(angles_dict, mode, duration)
		emit(
			"servo/transition_started",
			{
				"status": "ok",
				"message": f"Transition started for {transition_count} servos over {duration}s"
			}
		)
	except Exception as e:
		emit("error", {"status": "error", "message": str(e)})


@socketio.on("imu/start")
def ws_imu_start(data):
	global imu_stream_enabled, imu_stream_rate_hz
	try:
		payload = data or {}
		requested_rate = float(payload.get("rate_hz", imu_stream_rate_hz))
		with imu_stream_lock:
			imu_stream_rate_hz = max(1.0, min(200.0, requested_rate))
			imu_stream_enabled = True
		if not imu_reader.enabled:
			err = imu_reader.get_error_info()
			with imu_stream_lock:
				imu_stream_enabled = False
			_emit_imu_error(
				err["code"] or "IMU_NOT_AVAILABLE",
				"MPU6050 が利用できないため、ストリーミングを開始できません。",
				err["message"],
			)
			_emit_imu_status()
			return
		_ensure_imu_task_started()
		_emit_imu_status()
	except Exception as e:
		_emit_imu_error(
			"IMU_START_FAILED",
			"IMU ストリーミング開始リクエストの処理に失敗しました。",
			str(e),
		)


@socketio.on("imu/stop")
def ws_imu_stop():
	global imu_stream_enabled
	with imu_stream_lock:
		imu_stream_enabled = False
	_emit_imu_status()


@socketio.on("imu/set_rate")
def ws_imu_set_rate(data):
	global imu_stream_rate_hz
	try:
		payload = data or {}
		requested_rate = float(payload.get("rate_hz"))
		with imu_stream_lock:
			imu_stream_rate_hz = max(1.0, min(200.0, requested_rate))
		_emit_imu_status()
	except Exception as e:
		_emit_imu_error(
			"IMU_INVALID_RATE",
			"rate_hz は数値で指定してください（1〜200）。",
			str(e),
		)


@socketio.on("imu/status")
def ws_imu_status():
	_emit_imu_status()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servo daemon (Socket.IO / WebSocket のみ)")
    parser.add_argument(
        "--access-log",
        action="store_true",
        help="Werkzeug の HTTP アクセスログを出す（Socket.IO ハンドシェイク等）。デフォルトはオフ。",
    )
    args = parser.parse_args()
    if not args.access_log:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)