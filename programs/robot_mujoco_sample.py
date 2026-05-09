# type: ignore

import time
import mujoco
import mujoco.viewer

# Yuuki Lab robot - rough MuJoCo lower-body prototype
# ---------------------------------------------------
# This is NOT an exact model. It is a first approximation based on photos:
# - two legs
# - large rectangular feet
# - hip / knee / ankle joints
# - simple basket-like torso mass
#
# Goal of this file:
# 1. Confirm MuJoCo runs
# 2. Create a rough standing robot
# 3. Provide a base that can be refined with real dimensions, mass, servo limits, and logs

XML = r"""
<mujoco model="yuuki_robot_rough">
  <compiler angle="degree" coordinate="local"/>

  <option timestep="0.002" gravity="0 0 -9.81" integrator="RK4"/>

  <default>
    <joint damping="1.0" armature="0.02" limited="true"/>
    <geom friction="1.2 0.02 0.001" density="500" rgba="0.75 0.75 0.75 1"/>
    <motor ctrllimited="true" ctrlrange="-1 1"/>
  </default>

  <asset>
    <texture name="grid" type="2d" builtin="checker" width="512" height="512" rgb1="0.2 0.2 0.2" rgb2="0.3 0.3 0.3"/>
    <material name="floor_mat" texture="grid" texrepeat="8 8"/>
    <material name="metal" rgba="0.7 0.7 0.7 1"/>
    <material name="servo" rgba="0.65 0.1 0.18 1"/>
    <material name="basket" rgba="0.85 0.82 0.7 1"/>
  </asset>

  <worldbody>
    <light pos="0 -3 4" dir="0 1 -1" diffuse="0.8 0.8 0.8"/>
    <geom name="floor" type="plane" size="3 3 0.05" material="floor_mat"/>

    <!-- Floating base: first prototype uses free joint so it can fall naturally. -->
    <body name="torso" pos="0 0 0.95">
      <freejoint name="root"/>

      <!-- Basket / upper mass approximation -->
      <geom name="basket_box" type="box" size="0.23 0.13 0.12" pos="0 0 0.08" material="basket" mass="2.0"/>
      <geom name="pelvis" type="box" size="0.16 0.08 0.04" pos="0 0 -0.10" material="metal" mass="0.8"/>

      <!-- Left leg -->
      <body name="left_hip" pos="0 0.095 -0.12">
        <joint name="left_hip_roll" type="hinge" axis="1 0 0" range="-35 35" damping="2"/>
        <geom name="left_hip_servo" type="box" size="0.045 0.035 0.035" material="servo" mass="0.25"/>

        <body name="left_thigh" pos="0 0 -0.16">
          <joint name="left_hip_pitch" type="hinge" axis="0 1 0" range="-60 60" damping="2"/>
          <geom name="left_thigh_link" type="capsule" fromto="0 0 0  0 0 -0.30" size="0.025" material="metal" mass="0.7"/>

          <body name="left_shin" pos="0 0 -0.32">
            <joint name="left_knee_pitch" type="hinge" axis="0 1 0" range="-90 10" damping="2"/>
            <geom name="left_knee_servo" type="box" size="0.045 0.035 0.035" material="servo" mass="0.25"/>
            <geom name="left_shin_link" type="capsule" fromto="0 0 0  0 0 -0.28" size="0.023" material="metal" mass="0.6"/>

            <body name="left_ankle" pos="0 0 -0.30">
              <joint name="left_ankle_pitch" type="hinge" axis="0 1 0" range="-45 45" damping="2"/>
              <geom name="left_ankle_servo" type="box" size="0.045 0.035 0.035" material="servo" mass="0.25"/>
    
              <body name="left_foot" pos="0.05 0 -0.06">
                <joint name="left_ankle_roll" type="hinge" axis="1 0 0" range="-25 25" damping="2"/>
                <!-- Large aluminum foot plate approximation -->
                <geom name="left_foot_plate" type="box" size="0.16 0.09 0.01" pos="0.06 0 -0.015" material="metal" mass="0.8" friction="1.5 0.02 0.001"/>
              </body>
            </body>
          </body>
        </body>
      </body>

      <!-- Right leg -->
      <body name="right_hip" pos="0 -0.095 -0.12">
        <joint name="right_hip_roll" type="hinge" axis="1 0 0" range="-35 35" damping="2"/>
        <geom name="right_hip_servo" type="box" size="0.045 0.035 0.035" material="servo" mass="0.25"/>

        <body name="right_thigh" pos="0 0 -0.16">
          <joint name="right_hip_pitch" type="hinge" axis="0 1 0" range="-60 60" damping="2"/>
          <geom name="right_thigh_link" type="capsule" fromto="0 0 0  0 0 -0.30" size="0.025" material="metal" mass="0.7"/>

          <body name="right_shin" pos="0 0 -0.32">
            <joint name="right_knee_pitch" type="hinge" axis="0 1 0" range="-90 10" damping="2"/>
            <geom name="right_knee_servo" type="box" size="0.045 0.035 0.035" material="servo" mass="0.25"/>
            <geom name="right_shin_link" type="capsule" fromto="0 0 0  0 0 -0.28" size="0.023" material="metal" mass="0.6"/>

            <body name="right_ankle" pos="0 0 -0.30">
              <joint name="right_ankle_pitch" type="hinge" axis="0 1 0" range="-45 45" damping="2"/>
              <geom name="right_ankle_servo" type="box" size="0.045 0.035 0.035" material="servo" mass="0.25"/>

              <body name="right_foot" pos="0.05 0 -0.06">
                <joint name="right_ankle_roll" type="hinge" axis="1 0 0" range="-25 25" damping="2"/>
                <geom name="right_foot_plate" type="box" size="0.16 0.09 0.01" pos="0.06 0 -0.015" material="metal" mass="0.8" friction="1.5 0.02 0.001"/>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>
  </worldbody>

  <actuator>
    <!-- Gear values are rough. Later, tune from actual servo torque and control behavior. -->
    <motor name="m_left_hip_roll" joint="left_hip_roll" gear="80"/>
    <motor name="m_left_hip_pitch" joint="left_hip_pitch" gear="80"/>
    <motor name="m_left_knee_pitch" joint="left_knee_pitch" gear="80"/>
    <motor name="m_left_ankle_pitch" joint="left_ankle_pitch" gear="60"/>
    <motor name="m_left_ankle_roll" joint="left_ankle_roll" gear="60"/>

    <motor name="m_right_hip_roll" joint="right_hip_roll" gear="80"/>
    <motor name="m_right_hip_pitch" joint="right_hip_pitch" gear="80"/>
    <motor name="m_right_knee_pitch" joint="right_knee_pitch" gear="80"/>
    <motor name="m_right_ankle_pitch" joint="right_ankle_pitch" gear="60"/>
    <motor name="m_right_ankle_roll" joint="right_ankle_roll" gear="60"/>
  </actuator>
</mujoco>
"""


def main():
    model = mujoco.MjModel.from_xml_string(XML)
    data = mujoco.MjData(model)

    # Start from the XML pose. Let it settle/fall naturally.
    # Later we will add position control to hold servo angles.
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            # Example: very small hip roll command to test left/right weight shift.
            # data.ctrl[0] = 0.05
            # data.ctrl[5] = -0.05

            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(model.opt.timestep)


if __name__ == "__main__":
    main()
