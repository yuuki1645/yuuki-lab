# type: ignore

import mujoco
import mujoco.viewer
import time
import numpy as np
from flask import Flask
from flask_socketio import SocketIO
import threading



def _sensor_vec(name: str, dim: int) -> np.ndarray:
  sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, name)
  adr = int(model.sensor_adr[sid])
  return np.asarray(data.sensordata[adr : adr + dim], dtype=np.float32).copy()

def _acc_sensor_ms2_to_g(acc_ms2: np.ndarray) -> np.ndarray:
  g_mag = float(np.linalg.norm(model.opt.gravity))
  if not np.isfinite(g_mag) or g_mag < 1e-6:
    g_mag = 9.80665
  return acc_ms2 / np.float32(g_mag)


model = mujoco.MjModel.from_xml_path("../mujoco_sim_assets/xmls/004_leg_1joint/main.xml")
data = mujoco.MjData(model)




app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

acc = np.zeros(3, dtype=np.float32)

@socketio.on("connect")
def _on_connect():
  from flask_socketio import emit
  emit("rl_telemetry/hello", {"ok": True, "server_ts": time.time()})

def _drain_loop():
  global acc

  while True:
    socketio.emit(
      "rl_telemetry/step",
      {"obs_acc": acc.tolist(), "obs_acc_unit": "g"},
    )
    time.sleep(0.1)

def _run_blocking():
  socketio.start_background_task(_drain_loop)
  socketio.run(app, host="0.0.0.0", port=8791, debug=False)

thread = threading.Thread(target=_run_blocking, daemon=True)
thread.start()

step = 0

with mujoco.viewer.launch_passive(model, data) as viewer:
  while viewer.is_running():
    # print(f"step: {step}")
    step += 1
    mujoco.mj_step(model, data)

    print(f"data.time: {data.time}")

    # IMU センサーデータを取得
    acc_ms2 = _sensor_vec("imu_acc", 3)
    acc = _acc_sensor_ms2_to_g(acc_ms2)
    print(f"acc: {acc}")


    viewer.sync()

    timestep = model.opt.timestep
    print(f"timestep: {timestep}")
    time.sleep(timestep)
    # time.sleep(1)