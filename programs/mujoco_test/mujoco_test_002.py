# type: ignore

import mujoco
import mujoco.viewer
import time
import math

model = mujoco.MjModel.from_xml_path("xmls/main.xml")
data = mujoco.MjData(model)

# actuator名からid取得
left_knee_id = mujoco.mj_name2id(
    model,
    mujoco.mjtObj.mjOBJ_ACTUATOR,
    "left_knee_motor",
)

with mujoco.viewer.launch_passive(model, data) as viewer:
    start = time.time()

    while viewer.is_running():
        t = time.time() - start

        # 角度指定：sinでゆっくり膝を動かす
        target_angle = 0.4 * math.sin(t)

        # position actuator の目標角度を指定
        data.ctrl[left_knee_id] = target_angle

        mujoco.mj_step(model, data)
        viewer.sync()
        time.sleep(model.opt.timestep)