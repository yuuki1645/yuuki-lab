# type: ignore

import mujoco
import mujoco.viewer
import time


model = mujoco.MjModel.from_xml_path("../mujoco_sim_assets/xmls/005_leg_1joint/main.xml")
data = mujoco.MjData(model)

model.vis.map.alpha = 0.5
model.vis.scale.jointlength = 0.3
model.vis.scale.jointwidth = 0.1
model.vis.scale.framelength = 0.8
model.vis.scale.framewidth = 0.04
model.vis.scale.com = 0.1
model.vis.rgba.com = (1, 0, 0, 1)
model.vis.headlight.ambient = 0.5
model.vis.headlight.diffuse = 1
model.vis.headlight.specular = 1

with mujoco.viewer.launch_passive(model, data) as viewer:
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_JOINT] = 1
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = 1
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_COM] = 1
  viewer.opt.label = mujoco.mjtLabel.mjLABEL_GEOM
  viewer.opt.frame = mujoco.mjtFrame.mjFRAME_BODY

  while viewer.is_running():
    mujoco.mj_step(model, data)
    viewer.sync()
    time.sleep(model.opt.timestep)