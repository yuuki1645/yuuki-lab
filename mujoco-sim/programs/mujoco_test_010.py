# type: ignore

import mujoco
import mujoco.viewer
import time
from mujoco_sim_common.viewer_visual_presets import apply_model_visual_preset, apply_passive_viewer_options
import math
import sys


count = 0

def xprint(print_str: str):
  global count

  if count == 10:
    # print(print_str, end="\r", flush=True)
    print(print_str, end="")
    count = 0

  count += 1


def _knee_angle_to_logical_deg(knee_angle: float) -> float:
  return math.degrees(knee_angle)

def _ankle_angle_to_logical_deg(ankle_angle: float) -> float:
  return math.degrees(ankle_angle)


model = mujoco.MjModel.from_xml_path("../mujoco_sim_assets/xmls/007_leg_2joint/main.xml")
data = mujoco.MjData(model)


apply_model_visual_preset(model)

with mujoco.viewer.launch_passive(model, data) as viewer:
  apply_passive_viewer_options(viewer)

  while viewer.is_running():
    mujoco.mj_step(model, data)
    viewer.sync()

    imu_z = data.site("imu_site").xpos[2]

    foot_z = data.site("foot_site").xpos[2]

    foot_xaxis = data.sensor("foot_xaxis").data.copy()  
    foot_zaxis = data.sensor("foot_zaxis").data.copy()
    toe_pos = data.sensor("toe_pos").data.copy()

    knee_angle = data.joint("knee").qpos[0]
    ankle_angle = data.joint("ankle").qpos[0]

    knee_angle_logical = _knee_angle_to_logical_deg(knee_angle)
    ankle_angle_logical = _ankle_angle_to_logical_deg(ankle_angle)

    com = data.subtree_com[model.body("basket_thigh").id]
    com_x = com[0] - toe_pos[0]
    com_z = com[2]

    # xprint(f"com: ({com[0]: 8.3f}, {com[1]: 8.3f}, {com[2]: 8.3f})")
    # xprint(f"knee_angle: {knee_angle: 8.3f} | ankle_angle: {ankle_angle: 8.3f} | imu_z: {imu_z: 8.3f} | foot_zaxis: ({foot_zaxis[0]: 8.3f}, {foot_zaxis[1]: 8.3f}, {foot_zaxis[2]: 8.3f})")

    xprint(
      f"imu_z        : {imu_z: 8.3f}\n"
      f"foot_z       : {foot_z: 8.3f}\n"
      f"foot_xaxis_x : {foot_xaxis[2]: 8.3f}\n"
      f"knee         : {knee_angle_logical: 6.1f}°  ({knee_angle: 8.3f})\n"
      f"ankle        : {ankle_angle_logical: 6.1f}°  ({ankle_angle: 8.3f})\n"
      f"com_x        : {com_x: 8.3f}\n"
      f"com_z        : {com_z: 8.3f}\033[6A\r"
    )

    time.sleep(model.opt.timestep)