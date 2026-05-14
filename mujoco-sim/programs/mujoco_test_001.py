# type: ignore

import mujoco
import mujoco.viewer
import time


model = mujoco.MjModel.from_xml_path("../mujoco_sim_assets/xmls/005_leg_1joint/main.xml")
data = mujoco.MjData(model)

with mujoco.viewer.launch_passive(model, data) as viewer:
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_JOINT] = 1
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = 1
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CENTEROFMASS] = 1
  viewer.opt.frame = mujoco.mjtFrame.mjFRAME_BODY

  while viewer.is_running():
    mujoco.mj_step(model, data)
    viewer.sync()
    time.sleep(model.opt.timestep)