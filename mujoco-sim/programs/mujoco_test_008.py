# type: ignore

import mujoco
import mujoco.viewer


model = mujoco.MjModel.from_xml_path("../mujoco_sim_assets/xmls/005_leg_1joint/main.xml")
data = mujoco.MjData(model)

mujoco.viewer.launch(model, data)
