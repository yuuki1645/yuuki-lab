from flask import Flask, jsonify, request
import json
from servo import SERVO_MAP, move_servo_logical, move_servo_physical
from kinematics import KINEMATICS

state_path = "./state.json"

app = Flask(__name__)

def _load_state():
	global state
	try:
		with open(state_path, "r") as f:
			state = json.load(f)
		return state
	except Exception:
		return {}

def _save_state():
	global state
	with open(state_path, "w") as f:
		json.dump(state, f, ensure_ascii=False, indent=4)

state = _load_state()

@app.get("/state")
def get_state():
	return state

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

@app.get("/set_logical")
def set_logical():
	ch = int(request.args.get("ch"))
	logical_angle = float(request.args.get("l_ang"))
	result = move_servo_logical(SERVO_CH_2_NAME[ch], logical_angle)
	print("result:", result)
	state[str(ch)] = {
		"logical": result["logical"],
		"physical": result["physical"]
	}
	_save_state()
	return jsonify({"status": "ok"})

@app.get("/set_physical")
def set_physical():
	ch = int(request.args.get("ch"))
	physical_angle = float(request.args.get("p_ang"))
	result = move_servo_physical(SERVO_CH_2_NAME[ch], physical_angle)
	print("result:", result)
	state[str(ch)] = {
		"logical": result["logical"],
		"physical": result["physical"]
	}
	_save_state()
	return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)