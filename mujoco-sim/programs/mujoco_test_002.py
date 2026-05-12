# type: ignore

import mujoco
import mujoco.viewer
import time
import numpy as np


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

with mujoco.viewer.launch_passive(model, data) as viewer:
  while viewer.is_running():
    mujoco.mj_step(model, data)

    # IMU センサーデータを取得
    acc_ms2 = _sensor_vec("imu_acc", 3)
    acc = _acc_sensor_ms2_to_g(acc_ms2)
    print(f"acc: {acc}")


    viewer.sync()
    time.sleep(model.opt.timestep)