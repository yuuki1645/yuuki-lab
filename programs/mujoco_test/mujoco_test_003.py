# type: ignore

import mujoco
import mujoco.viewer
import time

model = mujoco.MjModel.from_xml_path("xmls/main.xml")
data = mujoco.MjData(model)

with mujoco.viewer.launch_passive(model, data) as viewer:
  start = time.time()

  while viewer.is_running():
    t = time.time() - start

    mujoco.mj_step(model, data)
    viewer.sync()
    time.sleep(model.opt.timestep)