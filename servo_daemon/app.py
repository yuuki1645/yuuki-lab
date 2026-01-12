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

@app.get("/servos")
def get_servos():
	"""全サーボの情報と現在の状態を返す"""
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
			# 状態も含める
			"last_logical": servo_state.get("logical"),
			"last_physical": servo_state.get("physical"),
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)