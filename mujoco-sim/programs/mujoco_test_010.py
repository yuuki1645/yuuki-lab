# type: ignore

import mujoco
import mujoco.viewer
import time
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options

model = mujoco.MjModel.from_xml_path("../mujoco_sim_assets/xmls/007_leg_2joint/main.xml")
data = mujoco.MjData(model)

apply_model_visual_preset(model)

with mujoco.viewer.launch_passive(model, data) as viewer:
  apply_passive_viewer_options(viewer)

  while viewer.is_running():
    mujoco.mj_step(model, data)
    viewer.sync()
    time.sleep(model.opt.timestep)