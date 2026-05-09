# type: ignore

import time
import mujoco
import mujoco.viewer

XML = r"""
<mujoco>
  <asset>
    <texture name="grid" type="2d" builtin="checker" width="512" height="512" rgb1="0.2 0.2 0.2" rgb2="0.3 0.3 0.3"/>
    <material name="floor_mat" texture="grid" texrepeat="8 8"/>
  </asset>

  <worldbody>
    <geom type="plane" size="5 5 0.1" material="floor_mat"/>
  
    <body>
      <geom type="box" size="0.1 0.1 0.1" rgba="1 0 0 1"/>
    </body>
  </worldbody>
</mujoco>
"""

def main():
  model = mujoco.MjModel.from_xml_string(XML)
  data = mujoco.MjData(model)

  with mujoco.viewer.launch_passive(model, data) as viewer:
    while viewer.is_running():
      mujoco.mj_step(model, data)
      viewer.sync()
      time.sleep(model.opt.timestep)

if __name__ == "__main__":
  main()