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

    knee_angle = data.joint("knee").qpos[0]
    ankle_angle = data.joint("ankle").qpos[0]
    imu_z = data.site("imu_site").xpos[2]
    foot_zaxis = data.sensor("foot_zaxis").data.copy()

    print(f"knee_angle: {knee_angle: 8.3f} | ankle_angle: {ankle_angle: 8.3f} | imu_z: {imu_z: 8.3f} | foot_zaxis: ({foot_zaxis[0]: 8.3f}, {foot_zaxis[1]: 8.3f}, {foot_zaxis[2]: 8.3f})")

    time.sleep(model.opt.timestep)