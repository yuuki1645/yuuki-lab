# type: ignore

import mujoco
import mujoco.viewer
import time

xml = """
<mujoco>
  <option gravity="0 0 -9.81"/>

  <worldbody>
    <light pos="0 0 3"/>
    <body name="pendulum" pos="0 0 1">
      <joint name="hinge" type="hinge" axis="0 1 0"/>
      <geom type="capsule" fromto="0 0 0  0 0 -0.8" size="0.04" mass="1"/>
    </body>
  </worldbody>
</mujoco>
"""

model = mujoco.MjModel.from_xml_string(xml)
data = mujoco.MjData(model)

# 初期角度を少し傾ける
data.qpos[0] = 0.7

with mujoco.viewer.launch_passive(model, data) as viewer:
    while viewer.is_running():
        mujoco.mj_step(model, data)
        viewer.sync()
        time.sleep(model.opt.timestep)