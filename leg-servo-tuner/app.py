# app.py
from flask import Flask, render_template, request, jsonify
from servo import move_servo, SERVO_MAP

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", servos=SERVO_MAP.keys())


@app.post("/api/move")
def api_move():
    data = request.json
    servo = data["servo"]
    angle = float(data["angle"])

    print(f"[DEBUG] servo={servo}, angle={angle}")

    move_servo(servo, angle)

    return jsonify({
        "status": "ok",
        "servo": servo,
        "angle": angle
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
