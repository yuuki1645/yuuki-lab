from flask import Flask, jsonify, request
from servo import SERVO_MAP, move_servo_logical, move_servo_physical
from kinematics import KINEMATICS
from state_manager import StateManager

app = Flask(__name__)

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

@app.get("/state")
def get_state():
	"""現在の状態を返す"""
	return jsonify(state_manager.get_all())

@app.get("/servos")
def get_servos():
	"""全サーボの情報を返す"""
	servos = []
	for name, ch in SERVO_MAP.items():
		kin = KINEMATICS[name]
		servos.append({
			"name": name,
			"ch": ch,
			"logical_lo": kin.logical_range.lo,
			"logical_hi": kin.logical_range.hi,
			"physical_min": kin.physical_range.lo,
			"physical_max": kin.physical_range.hi,
			"default_logical": kin.default_logical,
			"default_physical": kin.default_physical,
		})
	return jsonify({"servos": servos})

def _set_servo_angle(ch: int, angle: float, mode: str):
	"""サーボ角度を設定する共通処理"""
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
	
	# 全ての状態を返す
	return jsonify({
		"status": "ok",
		"state": state_manager.get_all() # 全ての状態を返す
	})

@app.get("/set_logical")
def set_logical():
	ch = int(request.args.get("ch"))
	logical_angle = float(request.args.get("l_ang"))
	servo_name = SERVO_CH_2_NAME[ch]
	print(f"[SERVO] set_logical - {servo_name} (ch={ch}): logical={logical_angle}")
	return _set_servo_angle(ch, logical_angle, "logical")

@app.get("/set_physical")
def set_physical():
	ch = int(request.args.get("ch"))
	physical_angle = float(request.args.get("p_ang"))
	servo_name = SERVO_CH_2_NAME[ch]
	print(f"[SERVO] set_physical - {servo_name} (ch={ch}): physical={physical_angle}")
	return _set_servo_angle(ch, physical_angle, "physical")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)