# type: ignore

import time

import mujoco
import mujoco.viewer
import numpy as np

from mujoco_sim_common.telemetry import HubTelemetrySocketIoServer


def _sensor_vec(model, data, name: str, dim: int) -> np.ndarray:
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, name)
    adr = int(model.sensor_adr[sid])
    return np.asarray(data.sensordata[adr : adr + dim], dtype=np.float32).copy()


def _acc_g(model, data) -> np.ndarray:
    acc_ms2 = _sensor_vec(model, data, "imu_acc", 3)
    g_mag = float(np.linalg.norm(model.opt.gravity))
    if not np.isfinite(g_mag) or g_mag < 1e-6:
        g_mag = 9.80665
    return acc_ms2 / np.float32(g_mag)


model = mujoco.MjModel.from_xml_path("../mujoco_sim_assets/xmls/004_leg_1joint/main.xml")
data = mujoco.MjData(model)

tel = HubTelemetrySocketIoServer(host="0.0.0.0", port=8791)
tel.start()
tel.publish_reset(
    {
        "wall_time": time.time(),
        "actuator_names": [],
        "obs_dim": 6,
        "obs_acc": [0.0, 0.0, 0.0],
        "obs_acc_unit": "g",
        "obs_gyro": [0.0, 0.0, 0.0],
        "obs_prev_ctrl": [],
        "obs_prev_action_logical_deg": [],
        "obs_prev_action_unit": "logical_deg",
        "obs_flat": [0.0] * 6,
        "num_timesteps": None,
    }
)

step_i = 0
with mujoco.viewer.launch_passive(model, data) as viewer:
    while viewer.is_running():
        mujoco.mj_step(model, data)
        step_i += 1
        acc = _acc_g(model, data)
        gyro = _sensor_vec(model, data, "imu_gyro", 3)
        obs_flat = np.concatenate([acc, gyro]).astype(np.float64)
        tel.publish_step(
            {
                "wall_time": time.time(),
                "episode_step": step_i,
                "num_timesteps": None,
                "actuator_names": [],
                "obs_acc": acc.tolist(),
                "obs_acc_unit": "g",
                "obs_gyro": gyro.tolist(),
                "obs_prev_ctrl": [],
                "obs_prev_action_logical_deg": [],
                "obs_prev_action_unit": "logical_deg",
                "obs_flat": obs_flat.tolist(),
                "action": [],
            }
        )
        viewer.sync()
        time.sleep(model.opt.timestep)
