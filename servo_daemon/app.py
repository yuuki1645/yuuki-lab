from flask import Flask, jsonify, request
from flask_cors import CORS
from servo import SERVO_MAP, move_servo_logical, move_servo_physical, move_servos_logical, move_servos_physical
from kinematics import KINEMATICS
from state_manager import StateManager
import time
import threading

app = Flask(__name__)
CORS(app)  # すべてのオリジンからのアクセスを許可

# 状態管理インスタンスを作成
state_manager = StateManager(state_path="./state.json")

SERVO_CH_2_NAME = {
	0: "R_HIP1",
	1: "R_HIP2",
	2: "R_KNEE",
	3: "R_HEEL",
	8: "L_HIP1",
	9: "L_HIP2",
	10: "L_KNEE",
	11: "L_HEEL",
}

@app.get("/servos")
def get_servos():
	"""全サーボの情報と現在の状態を返す"""
	state = state_manager.get_all()
	print("state: ", state)
	servos = []

	for name, ch in SERVO_MAP.items():
		kin = KINEMATICS[name]
		ch_str = str(ch)
		servo_state = state.get(ch_str, {})
		print("servo_state:", servo_state)

		servos.append({
			"name": name,
			"ch": ch,
			"logical_lo": kin.logical_range.lo,
			"logical_hi": kin.logical_range.hi,
			"physical_min": kin.physical_range.lo,
			"physical_max": kin.physical_range.hi,
			"default_logical": kin.default_logical,
			"default_physical": kin.default_physical,
			# 状態も含める
			"last_logical": servo_state.get("logical"),
			"last_physical": servo_state.get("physical"),
		})
	return jsonify({"servos": servos})

def _set_servo_angle(ch: int, angle: float, mode: str):
	"""サーボ角度を設定する共通処理（レスポンス付き）"""
	result = _set_servo_angle_internal(ch, angle, mode)
	
	# 軽量なレスポンスを返す
	return jsonify({
		"status": "ok",
	})

@app.post("/set")
def set_servo():
	"""
	サーボ角度を設定する（論理角・物理角の両方に対応）
	
	リクエストボディ（JSON）:
		{
			"ch": 0,           # チャンネル番号
			"mode": "logical", # "logical" または "physical"
			"angle": 90.0     # 角度
		}
	"""
	data = request.json or {}
	ch = int(data.get("ch"))
	mode = data.get("mode", "logical")
	angle = float(data.get("angle"))

	servo_name = SERVO_CH_2_NAME[ch]
	print(f"[SERVO] set_{mode} - {servo_name} (ch={ch}): {mode}={angle}")

	return _set_servo_angle(ch, angle, mode)

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
			print(f"[SERVO] SUCCESS - {', '.join(success_logs)}")
		
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

@app.post("/set_multiple")
def set_servos_multiple():
	"""
	複数のサーボ角度を一度に設定する
	
	リクエストボディ（JSON）:
		{
			"mode": "logical",  # "logical" または "physical"
			"angles": {          # チャンネル番号 -> 角度のマップ
				"0": 90.0,
				"1": 45.0,
				...
			}
		}
	"""
	data = request.json or {}
	mode = data.get("mode", "logical")
	angles = data.get("angles", {})
	
	# チャンネル番号を文字列からintに変換
	angles_dict = {int(ch_str): float(angle) for ch_str, angle in angles.items()}
	
	print(f"[SERVO] set_multiple_{mode} - {len(angles_dict)} servos")
	
	# 一括処理
	results = _set_servos_angles_internal(angles_dict, mode)
	
	return jsonify({
		"status": "ok",
		"success_count": len(results["success"]),
		"error_count": len(results["errors"]),
		"results": results
	})

@app.post("/transition")
def transition_servos():
	"""
	現在の角度から指定角度にゆっくり遷移させる
	
	リクエストボディ（JSON）:
		{
			"mode": "logical",  # "logical" または "physical"
			"angles": {          # チャンネル番号 -> 角度のマップ
				"0": 90.0,
				"1": 45.0,
				...
			},
			"duration": 3.0     # 遷移時間（秒）、デフォルト3.0
		}
	"""
	data = request.json or {}
	mode = data.get("mode", "logical")
	angles = data.get("angles", {})
	duration = float(data.get("duration", 3.0))
	
	# 現在の角度を取得
	state = state_manager.get_all()
	
	# 各サーボの現在角度と目標角度を計算
	transitions = {}
	for ch_str, target_angle in angles.items():
		ch = int(ch_str)
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
	
	# バックグラウンドで遷移を実行
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
	
	return jsonify({
		"status": "ok",
		"message": f"Transition started for {len(transitions)} servos over {duration}s"
	})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)